/*
 * fc_sched_bench — FC-farm shaped CPU contention probe.
 *
 * Two process roles share a farm node under a chosen OS policy:
 *   --mode batch         long CPU-bound workers (overnight FC place/CTS/route proxy)
 *   --mode interactive   wake→burst latency samples (debug / Vortex-query proxy)
 *
 * Orchestrators (scripts/) place each process in cgroups / nice / SCHED_BATCH.
 * This binary does NOT load a BPF sched_ext scheduler.
 *
 * Build: make
 */

#define _GNU_SOURCE
#include <errno.h>
#include <getopt.h>
#include <inttypes.h>
#include <pthread.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t g_stop = 0;

static void on_sig(int sig)
{
	(void)sig;
	g_stop = 1;
}

static uint64_t nsec_now(void)
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

static void burn_ns(uint64_t ns)
{
	uint64_t t0 = nsec_now();
	uint64_t x = 0x9e3779b97f4a7c15ull;
	while (nsec_now() - t0 < ns) {
		x ^= x << 13;
		x ^= x >> 7;
		x ^= x << 17;
		x += 0x85ebca6b;
	}
	asm volatile("" : "+r"(x));
}

struct batch_args {
	uint64_t duration_ns;
	uint64_t burst_ns;
	uint64_t iters;
};

static void *batch_thread(void *arg)
{
	struct batch_args *a = arg;
	uint64_t t0 = nsec_now();
	uint64_t iters = 0;
	while (!g_stop && (nsec_now() - t0) < a->duration_ns) {
		burn_ns(a->burst_ns);
		iters++;
	}
	a->iters = iters;
	return NULL;
}

static int cmp_u64(const void *xa, const void *xb)
{
	uint64_t a = *(const uint64_t *)xa;
	uint64_t b = *(const uint64_t *)xb;
	return (a > b) - (a < b);
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

static void usage(const char *argv0)
{
	fprintf(stderr,
		"Usage:\n"
		"  %s --mode batch --duration-s N [--workers N] [--burst-us N] [--label S] [--json P]\n"
		"  %s --mode burn --duration-s N [--burst-us N] [--label S] [--json P]\n"
		"  %s --mode interactive --duration-s N [--period-us N] [--burst-us N] [--label S] [--json P]\n",
		argv0, argv0, argv0);
}

int main(int argc, char **argv)
{
	const char *mode = NULL;
	int duration_s = 20;
	int workers = -1;
	int burst_us = -1;
	int period_us = 10000;
	const char *label = "unnamed";
	const char *json_path = NULL;

	static struct option longopts[] = {
		{"mode", required_argument, 0, 'm'},
		{"duration-s", required_argument, 0, 'd'},
		{"workers", required_argument, 0, 'w'},
		{"burst-us", required_argument, 0, 'b'},
		{"period-us", required_argument, 0, 'p'},
		{"label", required_argument, 0, 'l'},
		{"json", required_argument, 0, 'j'},
		{"help", no_argument, 0, 'h'},
		{0, 0, 0, 0},
	};

	int c;
	while ((c = getopt_long(argc, argv, "m:d:w:b:p:l:j:h", longopts, NULL)) != -1) {
		switch (c) {
		case 'm':
			mode = optarg;
			break;
		case 'd':
			duration_s = atoi(optarg);
			break;
		case 'w':
			workers = atoi(optarg);
			break;
		case 'b':
			burst_us = atoi(optarg);
			break;
		case 'p':
			period_us = atoi(optarg);
			break;
		case 'l':
			label = optarg;
			break;
		case 'j':
			json_path = optarg;
			break;
		case 'h':
		default:
			usage(argv[0]);
			return c == 'h' ? 0 : 1;
		}
	}

	if (!mode) {
		usage(argv[0]);
		return 1;
	}

	signal(SIGINT, on_sig);
	signal(SIGTERM, on_sig);

	long ncpu = sysconf(_SC_NPROCESSORS_ONLN);
	if (ncpu < 1)
		ncpu = 1;
	uint64_t duration_ns = (uint64_t)duration_s * 1000000000ull;

	if (strcmp(mode, "batch") == 0) {
		if (workers < 0) {
			workers = (int)ncpu - 1;
			if (workers < 1)
				workers = 1;
		}
		if (burst_us < 0)
			burst_us = 2000;

		struct batch_args *args = calloc((size_t)workers, sizeof(*args));
		pthread_t *tids = calloc((size_t)workers, sizeof(*tids));
		if (!args || !tids) {
			perror("calloc");
			return 1;
		}

		fprintf(stderr, "# batch label=%s cpus=%ld workers=%d duration_s=%d burst_us=%d\n",
			label, ncpu, workers, duration_s, burst_us);

		uint64_t t0 = nsec_now();
		for (int i = 0; i < workers; i++) {
			args[i].duration_ns = duration_ns;
			args[i].burst_ns = (uint64_t)burst_us * 1000ull;
			if (pthread_create(&tids[i], NULL, batch_thread, &args[i]) != 0) {
				perror("pthread_create");
				return 1;
			}
		}
		for (int i = 0; i < workers; i++)
			pthread_join(tids[i], NULL);
		uint64_t t1 = nsec_now();
		double wall_s = (double)(t1 - t0) / 1e9;

		uint64_t iters = 0;
		for (int i = 0; i < workers; i++)
			iters += args[i].iters;
		double rate = wall_s > 0 ? (double)iters / wall_s : 0.0;

		printf("role=batch label=%s wall_s=%.3f iters=%" PRIu64 " iters_per_s=%.2f workers=%d\n",
		       label, wall_s, iters, rate, workers);

		if (json_path) {
			FILE *f = fopen(json_path, "w");
			if (!f) {
				perror("fopen");
				return 1;
			}
			fprintf(f,
				"{\n"
				"  \"role\": \"batch\",\n"
				"  \"label\": \"%s\",\n"
				"  \"cpus\": %ld,\n"
				"  \"workers\": %d,\n"
				"  \"duration_s\": %d,\n"
				"  \"burst_us\": %d,\n"
				"  \"wall_s\": %.6f,\n"
				"  \"iters\": %" PRIu64 ",\n"
				"  \"iters_per_s\": %.6f\n"
				"}\n",
				label, ncpu, workers, duration_s, burst_us, wall_s, iters, rate);
			fclose(f);
		}
		free(args);
		free(tids);
		return 0;
	}

	if (strcmp(mode, "interactive") == 0 || strcmp(mode, "burn") == 0) {
		/* interactive: paced wake→burst (latency). burn: always-runnable (share). */
		int is_burn = strcmp(mode, "burn") == 0;
		if (burst_us < 0)
			burst_us = is_burn ? 2000 : 500;

		if (is_burn) {
			/* Always-runnable single thread — fair-share / weight probe. */
			uint64_t burst_ns = (uint64_t)burst_us * 1000ull;
			uint64_t t0 = nsec_now();
			uint64_t iters = 0;
			fprintf(stderr, "# burn label=%s cpus=%ld duration_s=%d burst_us=%d\n",
				label, ncpu, duration_s, burst_us);
			while (!g_stop && (nsec_now() - t0) < duration_ns) {
				burn_ns(burst_ns);
				iters++;
			}
			uint64_t t1 = nsec_now();
			double wall_s = (double)(t1 - t0) / 1e9;
			double rate = wall_s > 0 ? (double)iters / wall_s : 0.0;
			/* 1.0 == fully occupied one CPU given burst_us quantum. */
			double cpu_eq = rate * ((double)burst_us / 1e6);

			printf("role=burn label=%s wall_s=%.3f iters=%" PRIu64 " iters_per_s=%.2f cpu_eq=%.3f\n",
			       label, wall_s, iters, rate, cpu_eq);

			if (json_path) {
				FILE *f = fopen(json_path, "w");
				if (!f) {
					perror("fopen");
					return 1;
				}
				fprintf(f,
					"{\n"
					"  \"role\": \"burn\",\n"
					"  \"label\": \"%s\",\n"
					"  \"cpus\": %ld,\n"
					"  \"duration_s\": %d,\n"
					"  \"burst_us\": %d,\n"
					"  \"wall_s\": %.6f,\n"
					"  \"iters\": %" PRIu64 ",\n"
					"  \"iters_per_s\": %.6f,\n"
					"  \"cpu_eq\": %.6f\n"
					"}\n",
					label, ncpu, duration_s, burst_us, wall_s, iters, rate, cpu_eq);
				fclose(f);
			}
			return 0;
		}

		size_t cap = (size_t)duration_s * 1000000ull / (size_t)period_us + 64;
		uint64_t *lats = calloc(cap, sizeof(*lats));
		if (!lats) {
			perror("calloc");
			return 1;
		}

		fprintf(stderr,
			"# interactive label=%s cpus=%ld duration_s=%d period_us=%d burst_us=%d\n",
			label, ncpu, duration_s, period_us, burst_us);

		uint64_t t0 = nsec_now();
		size_t n = 0;
		while (!g_stop && (nsec_now() - t0) < duration_ns) {
			uint64_t wake = nsec_now();
			burn_ns((uint64_t)burst_us * 1000ull);
			uint64_t done = nsec_now();
			if (n < cap)
				lats[n++] = done - wake;
			uint64_t elapsed = nsec_now() - wake;
			uint64_t period_ns = (uint64_t)period_us * 1000ull;
			if (elapsed < period_ns) {
				struct timespec req = {.tv_sec = 0, .tv_nsec = (long)(period_ns - elapsed)};
				nanosleep(&req, NULL);
			}
		}
		uint64_t t1 = nsec_now();
		double wall_s = (double)(t1 - t0) / 1e9;

		qsort(lats, n, sizeof(*lats), cmp_u64);
		uint64_t p50 = percentile(lats, n, 50);
		uint64_t p95 = percentile(lats, n, 95);
		uint64_t p99 = percentile(lats, n, 99);
		uint64_t p999 = percentile(lats, n, 99.9);
		uint64_t pmax = n ? lats[n - 1] : 0;
		/* Outlier: wall latency > 1.5x requested burst (preemption / queueing). */
		uint64_t thresh = (uint64_t)burst_us * 1500ull; /* 1.5x in ns */
		size_t outliers = 0;
		for (size_t i = 0; i < n; i++) {
			if (lats[i] > thresh)
				outliers++;
		}
		double outlier_ppm = n ? (1e6 * (double)outliers / (double)n) : 0.0;

		printf("role=interactive label=%s wall_s=%.3f samples=%zu p50_us=%.1f p95_us=%.1f "
		       "p99_us=%.1f p999_us=%.1f max_us=%.1f outliers=%zu outlier_ppm=%.1f\n",
		       label, wall_s, n, p50 / 1e3, p95 / 1e3, p99 / 1e3, p999 / 1e3, pmax / 1e3,
		       outliers, outlier_ppm);

		if (json_path) {
			FILE *f = fopen(json_path, "w");
			if (!f) {
				perror("fopen");
				return 1;
			}
			fprintf(f,
				"{\n"
				"  \"role\": \"interactive\",\n"
				"  \"label\": \"%s\",\n"
				"  \"cpus\": %ld,\n"
				"  \"duration_s\": %d,\n"
				"  \"period_us\": %d,\n"
				"  \"burst_us\": %d,\n"
				"  \"wall_s\": %.6f,\n"
				"  \"samples\": %zu,\n"
				"  \"p50_us\": %.3f,\n"
				"  \"p95_us\": %.3f,\n"
				"  \"p99_us\": %.3f,\n"
				"  \"p999_us\": %.3f,\n"
				"  \"max_us\": %.3f,\n"
				"  \"outliers\": %zu,\n"
				"  \"outlier_ppm\": %.3f\n"
				"}\n",
				label, ncpu, duration_s, period_us, burst_us, wall_s, n, p50 / 1e3,
				p95 / 1e3, p99 / 1e3, p999 / 1e3, pmax / 1e3, outliers, outlier_ppm);
			fclose(f);
		}
		free(lats);
		return 0;
	}

	fprintf(stderr, "unknown mode: %s\n", mode);
	usage(argv[0]);
	return 1;
}
