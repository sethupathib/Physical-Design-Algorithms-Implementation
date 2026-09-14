/*
 * fanout_bench — fixed-work scheduler microbench for migration-cost A/B.
 *
 * Thesis under test (AMD epyc-eda rationale):
 *   Lower sched_migration_cost_ns lets runnable work spread onto idle cores
 *   faster after a transient imbalance. EDA farms often look like many
 *   short/uneven tasks; sticky migration cost can leave cores idle.
 *
 * Modes:
 *   spread  — start oversubscribed on a small CPU set, then unpin; measure
 *             makespan of remaining fixed work (primary CLAIM_GATE mode).
 *   queue   — shared job queue, T workers, M fixed-cost jobs; secondary.
 *
 * Output is machine-parseable KEY=VALUE lines on stdout.
 * This bench does NOT require tuned(8); pair with dump_sched_knobs.sh.
 */

#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <pthread.h>
#include <sched.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdatomic.h>
#include <time.h>
#include <unistd.h>

typedef struct {
	const char *mode;
	int threads;
	int pin_cpus;          /* spread: initial CPU count to pile onto */
	uint64_t work_units;   /* per-thread remaining work after unpin / per job */
	uint64_t jobs;         /* queue mode */
	int outer_iters;
	unsigned burn_iters;   /* inner spin iterations per work unit */
} config_t;

typedef struct {
	config_t cfg;
	pthread_barrier_t bar_start;
	pthread_barrier_t bar_unpin;
	volatile int go;
	volatile int unpin;
	atomic_uint_fast64_t jobs_done;
	atomic_uint_fast64_t job_index;
	double *thread_secs;
	cpu_set_t *initial_set;
} shared_t;

static double now_sec(void)
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (double)ts.tv_sec + 1e-9 * (double)ts.tv_nsec;
}

/* Fixed-cost burn — not wall-clock gated (preemption stretches latency honestly). */
static void burn_unit(unsigned iters)
{
	volatile uint64_t x = 1;
	for (unsigned i = 0; i < iters; i++) {
		x = x * 6364136223846793005ULL + 1ULL;
		x ^= x >> 17;
	}
	(void)x;
}

static int nproc_online(void)
{
	long n = sysconf(_SC_NPROCESSORS_ONLN);
	return n > 0 ? (int)n : 1;
}

static void die(const char *msg)
{
	perror(msg);
	exit(2);
}

typedef struct {
	shared_t *S;
	int tid;
} thread_arg_t;

static void *spread_worker(void *arg)
{
	thread_arg_t *A = arg;
	shared_t *S = A->S;
	int tid = A->tid;

	/* Pile onto initial CPU set. */
	if (pthread_setaffinity_np(pthread_self(), sizeof(cpu_set_t), S->initial_set) != 0)
		die("pthread_setaffinity_np initial");

	pthread_barrier_wait(&S->bar_start);

	/* Phase 1: fixed warm work while piled (creates cache/runqueue imbalance). */
	for (uint64_t i = 0; i < S->cfg.work_units / 8 + 1; i++)
		burn_unit(S->cfg.burn_iters);

	pthread_barrier_wait(&S->bar_unpin);

	/* Phase 2: unpin — scheduler may migrate. Remaining fixed work. */
	cpu_set_t all;
	CPU_ZERO(&all);
	int n = nproc_online();
	for (int c = 0; c < n; c++)
		CPU_SET(c, &all);
	if (pthread_setaffinity_np(pthread_self(), sizeof(cpu_set_t), &all) != 0)
		die("pthread_setaffinity_np unpin");

	double t0 = now_sec();
	for (uint64_t i = 0; i < S->cfg.work_units; i++)
		burn_unit(S->cfg.burn_iters);
	double t1 = now_sec();
	S->thread_secs[tid] = t1 - t0;
	return NULL;
}

static void *queue_worker(void *arg)
{
	thread_arg_t *A = arg;
	shared_t *S = A->S;
	int tid = A->tid;

	pthread_barrier_wait(&S->bar_start);
	double t0 = now_sec();
	for (;;) {
		uint64_t j = atomic_fetch_add(&S->job_index, 1);
		if (j >= S->cfg.jobs)
			break;
		burn_unit(S->cfg.burn_iters);
		/* Extra work units per job for heavier load. */
		for (uint64_t u = 1; u < S->cfg.work_units; u++)
			burn_unit(S->cfg.burn_iters);
		atomic_fetch_add(&S->jobs_done, 1);
	}
	double t1 = now_sec();
	S->thread_secs[tid] = t1 - t0;
	return NULL;
}

static void usage(const char *argv0)
{
	fprintf(stderr,
		"Usage: %s --mode spread|queue [options]\n"
		"  --threads N          worker threads (default: nproc)\n"
		"  --pin-cpus K         spread: initial pile width (default: max(1,nproc/4))\n"
		"  --work-units U       fixed units per thread/job (default: 2000)\n"
		"  --jobs M             queue mode job count (default: threads*64)\n"
		"  --burn-iters I       spin iters per unit (default: 8000)\n"
		"  --outer N            repeat and report median (default: 5)\n",
		argv0);
}

static int cmp_double(const void *a, const void *b)
{
	double da = *(const double *)a, db = *(const double *)b;
	return (da > db) - (da < db);
}

static double median(double *v, int n)
{
	qsort(v, (size_t)n, sizeof(double), cmp_double);
	if (n % 2)
		return v[n / 2];
	return 0.5 * (v[n / 2 - 1] + v[n / 2]);
}

static int parse_args(int argc, char **argv, config_t *c)
{
	c->mode = "spread";
	c->threads = nproc_online();
	c->pin_cpus = 0;
	c->work_units = 2000;
	c->jobs = 0;
	c->outer_iters = 5;
	c->burn_iters = 8000;

	for (int i = 1; i < argc; i++) {
		if (!strcmp(argv[i], "--mode") && i + 1 < argc)
			c->mode = argv[++i];
		else if (!strcmp(argv[i], "--threads") && i + 1 < argc)
			c->threads = atoi(argv[++i]);
		else if (!strcmp(argv[i], "--pin-cpus") && i + 1 < argc)
			c->pin_cpus = atoi(argv[++i]);
		else if (!strcmp(argv[i], "--work-units") && i + 1 < argc)
			c->work_units = strtoull(argv[++i], NULL, 10);
		else if (!strcmp(argv[i], "--jobs") && i + 1 < argc)
			c->jobs = strtoull(argv[++i], NULL, 10);
		else if (!strcmp(argv[i], "--burn-iters") && i + 1 < argc)
			c->burn_iters = (unsigned)atoi(argv[++i]);
		else if (!strcmp(argv[i], "--outer") && i + 1 < argc)
			c->outer_iters = atoi(argv[++i]);
		else if (!strcmp(argv[i], "--help")) {
			usage(argv[0]);
			exit(0);
		} else {
			usage(argv[0]);
			return -1;
		}
	}
	if (c->threads < 1)
		c->threads = 1;
	if (c->pin_cpus <= 0)
		c->pin_cpus = c->threads / 4 > 0 ? c->threads / 4 : 1;
	if (c->pin_cpus > nproc_online())
		c->pin_cpus = nproc_online();
	if (c->jobs == 0)
		c->jobs = (uint64_t)c->threads * 64ULL;
	if (c->outer_iters < 1)
		c->outer_iters = 1;
	return 0;
}

static double run_once(config_t *cfg)
{
	shared_t S;
	memset(&S, 0, sizeof(S));
	S.cfg = *cfg;
	S.thread_secs = calloc((size_t)cfg->threads, sizeof(double));
	if (!S.thread_secs)
		die("calloc");

	cpu_set_t init;
	CPU_ZERO(&init);
	for (int c = 0; c < cfg->pin_cpus; c++)
		CPU_SET(c, &init);
	S.initial_set = &init;

	if (pthread_barrier_init(&S.bar_start, NULL, (unsigned)cfg->threads + 1) != 0)
		die("barrier_start");
	if (!strcmp(cfg->mode, "spread")) {
		if (pthread_barrier_init(&S.bar_unpin, NULL, (unsigned)cfg->threads + 1) != 0)
			die("barrier_unpin");
	}

	pthread_t *th = calloc((size_t)cfg->threads, sizeof(pthread_t));
	thread_arg_t *args = calloc((size_t)cfg->threads, sizeof(thread_arg_t));
	if (!th || !args)
		die("calloc threads");

	void *(*fn)(void *) = !strcmp(cfg->mode, "queue") ? queue_worker : spread_worker;
	if (strcmp(cfg->mode, "spread") && strcmp(cfg->mode, "queue")) {
		fprintf(stderr, "unknown mode: %s\n", cfg->mode);
		exit(2);
	}

	for (int i = 0; i < cfg->threads; i++) {
		args[i].S = &S;
		args[i].tid = i;
		if (pthread_create(&th[i], NULL, fn, &args[i]) != 0)
			die("pthread_create");
	}

	double wall0 = now_sec();
	pthread_barrier_wait(&S.bar_start);
	if (!strcmp(cfg->mode, "spread"))
		pthread_barrier_wait(&S.bar_unpin);

	for (int i = 0; i < cfg->threads; i++)
		pthread_join(th[i], NULL);
	double wall1 = now_sec();

	double makespan = 0.0;
	for (int i = 0; i < cfg->threads; i++)
		if (S.thread_secs[i] > makespan)
			makespan = S.thread_secs[i];

	/* Prefer wall for queue (true completion); for spread use max thread phase-2. */
	double reported = !strcmp(cfg->mode, "queue") ? (wall1 - wall0) : makespan;

	pthread_barrier_destroy(&S.bar_start);
	if (!strcmp(cfg->mode, "spread"))
		pthread_barrier_destroy(&S.bar_unpin);
	free(S.thread_secs);
	free(th);
	free(args);
	return reported;
}

int main(int argc, char **argv)
{
	config_t cfg;
	if (parse_args(argc, argv, &cfg) != 0)
		return 2;

	double *samples = calloc((size_t)cfg.outer_iters, sizeof(double));
	if (!samples)
		die("calloc samples");

	/* Warmup */
	(void)run_once(&cfg);

	for (int i = 0; i < cfg.outer_iters; i++)
		samples[i] = run_once(&cfg);

	double med = median(samples, cfg.outer_iters);
	double lo = samples[0], hi = samples[cfg.outer_iters - 1];

	printf("bench=fanout\n");
	printf("mode=%s\n", cfg.mode);
	printf("nproc=%d\n", nproc_online());
	printf("threads=%d\n", cfg.threads);
	printf("pin_cpus=%d\n", cfg.pin_cpus);
	printf("work_units=%" PRIu64 "\n", cfg.work_units);
	printf("jobs=%" PRIu64 "\n", cfg.jobs);
	printf("burn_iters=%u\n", cfg.burn_iters);
	printf("outer=%d\n", cfg.outer_iters);
	printf("makespan_median_s=%.6f\n", med);
	printf("makespan_min_s=%.6f\n", lo);
	printf("makespan_max_s=%.6f\n", hi);
	printf("unit=seconds\n");
	free(samples);
	return 0;
}
