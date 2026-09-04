/*
 * fc_noise_bench — FC-shaped parallel CPU probe for OS-noise isolation demos.
 *
 * workers: N threads, R barrier-synchronized rounds of CPU burn;
 *          team round time = max(thread dts) that round → p50/p99/max.
 * noise:   burn + sleep/yield to contend for cores / caches.
 *
 * Build: cc -O2 -Wall -Wextra -pthread -o fc_noise_bench fc_noise_bench.c
 */

#define _GNU_SOURCE
#include <getopt.h>
#include <inttypes.h>
#include <pthread.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static uint64_t nsec_now(void)
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

/* Fixed-work burn: preemption stretches WALL time for the same iteration count.
 * (A wall-clock-gated spin would hide OS noise — rounds would still look ~burst_us.) */
static void burn_iters(uint64_t iters)
{
	uint64_t x = 0x9e3779b97f4a7c15ull;
	for (uint64_t i = 0; i < iters; i++) {
		x ^= x << 13;
		x ^= x >> 7;
		x ^= x << 17;
		x += 0x85ebca6b;
	}
	asm volatile("" : "+r"(x));
}

/* Calibrate iters ≈ target_ns of uninterrupted CPU on this host. */
static uint64_t calibrate_iters(uint64_t target_ns)
{
	uint64_t probe = 100000;
	for (int k = 0; k < 8; k++) {
		uint64_t t0 = nsec_now();
		burn_iters(probe);
		uint64_t dt = nsec_now() - t0;
		if (dt == 0)
			dt = 1;
		probe = (probe * target_ns) / dt;
		if (probe < 1000)
			probe = 1000;
	}
	return probe;
}

struct worker_args {
	int id;
	int rounds;
	uint64_t iters;
	pthread_barrier_t *bar;
	uint64_t *mine; /* length rounds */
};

static void *worker_main(void *arg)
{
	struct worker_args *a = arg;
	for (int r = 0; r < a->rounds; r++) {
		pthread_barrier_wait(a->bar);
		uint64_t t0 = nsec_now();
		burn_iters(a->iters);
		a->mine[r] = nsec_now() - t0;
		pthread_barrier_wait(a->bar);
	}
	return NULL;
}

static int cmp_u64(const void *a, const void *b)
{
	uint64_t x = *(const uint64_t *)a;
	uint64_t y = *(const uint64_t *)b;
	return (x > y) - (x < y);
}

static uint64_t percentile(uint64_t *sorted, size_t n, double p)
{
	if (n == 0)
		return 0;
	size_t idx = (size_t)((p / 100.0) * (double)(n - 1) + 0.5);
	if (idx >= n)
		idx = n - 1;
	return sorted[idx];
}

static void run_noise(int duration_s, uint64_t iters, uint64_t sleep_ns)
{
	uint64_t end = nsec_now() + (uint64_t)duration_s * 1000000000ull;
	while (nsec_now() < end) {
		burn_iters(iters);
		if (sleep_ns) {
			struct timespec ts = {.tv_sec = 0, .tv_nsec = (long)sleep_ns};
			nanosleep(&ts, NULL);
		} else {
			sched_yield();
		}
	}
}

static void usage(const char *argv0)
{
	fprintf(stderr,
		"Usage:\n"
		"  %s --mode workers --threads N --rounds R --burst-us U [--label S] [--json P]\n"
		"  %s --mode noise --duration-s S [--burst-us U] [--sleep-us U] [--label S]\n",
		argv0, argv0);
}

int main(int argc, char **argv)
{
	const char *mode = NULL;
	int threads = 2;
	int rounds = 200;
	int burst_us = 2000;
	int duration_s = 10;
	int sleep_us = 100;
	const char *label = "unnamed";
	const char *json_path = NULL;

	static struct option opts[] = {
		{"mode", required_argument, 0, 'm'},
		{"threads", required_argument, 0, 't'},
		{"rounds", required_argument, 0, 'r'},
		{"burst-us", required_argument, 0, 'b'},
		{"duration-s", required_argument, 0, 'd'},
		{"sleep-us", required_argument, 0, 's'},
		{"label", required_argument, 0, 'l'},
		{"json", required_argument, 0, 'j'},
		{"help", no_argument, 0, 'h'},
		{0, 0, 0, 0},
	};

	int c;
	while ((c = getopt_long(argc, argv, "m:t:r:b:d:s:l:j:h", opts, NULL)) != -1) {
		switch (c) {
		case 'm':
			mode = optarg;
			break;
		case 't':
			threads = atoi(optarg);
			break;
		case 'r':
			rounds = atoi(optarg);
			break;
		case 'b':
			burst_us = atoi(optarg);
			break;
		case 'd':
			duration_s = atoi(optarg);
			break;
		case 's':
			sleep_us = atoi(optarg);
			break;
		case 'l':
			label = optarg;
			break;
		case 'j':
			json_path = optarg;
			break;
		default:
			usage(argv[0]);
			return c == 'h' ? 0 : 1;
		}
	}

	if (!mode) {
		usage(argv[0]);
		return 1;
	}

	if (strcmp(mode, "noise") == 0) {
		uint64_t iters = calibrate_iters((uint64_t)burst_us * 1000ull);
		fprintf(stderr,
			"# noise label=%s duration_s=%d burst_us=%d sleep_us=%d iters=%" PRIu64 "\n",
			label, duration_s, burst_us, sleep_us, iters);
		run_noise(duration_s, iters, (uint64_t)sleep_us * 1000ull);
		printf("role=noise label=%s duration_s=%d\n", label, duration_s);
		return 0;
	}

	if (strcmp(mode, "workers") != 0) {
		fprintf(stderr, "unknown mode %s\n", mode);
		usage(argv[0]);
		return 1;
	}
	if (threads < 1 || rounds < 1)
		return 1;

	pthread_barrier_t bar;
	pthread_barrier_init(&bar, NULL, (unsigned)threads);

	uint64_t *all = calloc((size_t)threads * (size_t)rounds, sizeof(uint64_t));
	struct worker_args *args = calloc((size_t)threads, sizeof(*args));
	pthread_t *tids = calloc((size_t)threads, sizeof(*tids));
	uint64_t *team = calloc((size_t)rounds, sizeof(uint64_t));
	if (!all || !args || !tids || !team) {
		perror("calloc");
		return 1;
	}

	uint64_t iters = calibrate_iters((uint64_t)burst_us * 1000ull);
	fprintf(stderr,
		"# workers label=%s threads=%d rounds=%d burst_us=%d iters=%" PRIu64 "\n",
		label, threads, rounds, burst_us, iters);

	uint64_t wall0 = nsec_now();
	for (int i = 0; i < threads; i++) {
		args[i].id = i;
		args[i].rounds = rounds;
		args[i].iters = iters;
		args[i].bar = &bar;
		args[i].mine = all + (size_t)i * (size_t)rounds;
		if (pthread_create(&tids[i], NULL, worker_main, &args[i]) != 0) {
			perror("pthread_create");
			return 1;
		}
	}
	for (int i = 0; i < threads; i++)
		pthread_join(tids[i], NULL);
	uint64_t wall1 = nsec_now();
	double wall_s = (double)(wall1 - wall0) / 1e9;

	for (int r = 0; r < rounds; r++) {
		uint64_t mx = 0;
		for (int i = 0; i < threads; i++) {
			uint64_t v = all[(size_t)i * (size_t)rounds + (size_t)r];
			if (v > mx)
				mx = v;
		}
		team[r] = mx;
	}
	qsort(team, (size_t)rounds, sizeof(*team), cmp_u64);
	uint64_t p50 = percentile(team, (size_t)rounds, 50);
	uint64_t p95 = percentile(team, (size_t)rounds, 95);
	uint64_t p99 = percentile(team, (size_t)rounds, 99);
	uint64_t pmax = team[rounds - 1];

	printf("role=workers label=%s wall_s=%.3f threads=%d rounds=%d "
	       "round_p50_us=%.1f round_p95_us=%.1f round_p99_us=%.1f round_max_us=%.1f\n",
	       label, wall_s, threads, rounds, p50 / 1e3, p95 / 1e3, p99 / 1e3, pmax / 1e3);

	if (json_path) {
		FILE *f = fopen(json_path, "w");
		if (!f) {
			perror("fopen");
			return 1;
		}
		fprintf(f,
			"{\n"
			"  \"role\": \"workers\",\n"
			"  \"label\": \"%s\",\n"
			"  \"wall_s\": %.6f,\n"
			"  \"threads\": %d,\n"
			"  \"rounds\": %d,\n"
			"  \"burst_us\": %d,\n"
			"  \"round_p50_us\": %.3f,\n"
			"  \"round_p95_us\": %.3f,\n"
			"  \"round_p99_us\": %.3f,\n"
			"  \"round_max_us\": %.3f\n"
			"}\n",
			label, wall_s, threads, rounds, burst_us, p50 / 1e3, p95 / 1e3,
			p99 / 1e3, pmax / 1e3);
		fclose(f);
	}

	pthread_barrier_destroy(&bar);
	free(all);
	free(args);
	free(tids);
	free(team);
	return 0;
}
