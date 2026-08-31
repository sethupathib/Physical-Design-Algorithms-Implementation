/*
 * fc_io_bench — POSIX vs io_uring on Fusion-Compiler-shaped I/O.
 *
 * Backends:
 *   posix            — open + read loop
 *   iouring          — sync open + io_uring read (QD=64)
 *   iouring_openat   — io_uring openat + read (fewer syscalls on many-file)
 *
 * Scope: wrappers / stage-in / hydrate — NOT Synopsys FC internals.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <getopt.h>
#include <liburing.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#include <dirent.h>

#define MAX_FILES 100000
#define QD 64
#define BUF_CAP (8 * 1024 * 1024)

struct file_ent {
    char path[512];
    off_t size;
};

struct dataset {
    struct file_ent *files;
    int n;
    uint64_t total_bytes;
};

static double now_s(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

static void walk_add(struct dataset *ds, const char *path) {
    struct stat st;
    if (stat(path, &st) != 0 || !S_ISREG(st.st_mode)) return;
    if (ds->n >= MAX_FILES) return;
    snprintf(ds->files[ds->n].path, sizeof(ds->files[ds->n].path), "%s", path);
    ds->files[ds->n].size = st.st_size;
    ds->total_bytes += (uint64_t)st.st_size;
    ds->n++;
}

static void walk_dir(struct dataset *ds, const char *dir) {
    DIR *d = opendir(dir);
    if (!d) return;
    struct dirent *de;
    char path[768];
    while ((de = readdir(d)) != NULL) {
        if (de->d_name[0] == '.') continue;
        snprintf(path, sizeof(path), "%s/%s", dir, de->d_name);
        struct stat st;
        if (stat(path, &st) != 0) continue;
        if (S_ISDIR(st.st_mode)) walk_dir(ds, path);
        else if (S_ISREG(st.st_mode)) walk_add(ds, path);
    }
    closedir(d);
}

static int read_posix(struct dataset *ds, uint64_t *out_bytes) {
    uint64_t bytes = 0;
    unsigned char *buf = malloc(BUF_CAP);
    if (!buf) return -1;
    for (int i = 0; i < ds->n; i++) {
        int fd = open(ds->files[i].path, O_RDONLY);
        if (fd < 0) { free(buf); return -1; }
        off_t left = ds->files[i].size;
        while (left > 0) {
            size_t chunk = (size_t)((left > BUF_CAP) ? BUF_CAP : left);
            ssize_t n = read(fd, buf, chunk);
            if (n <= 0) { close(fd); free(buf); return -1; }
            left -= n;
            bytes += (uint64_t)n;
        }
        close(fd);
    }
    free(buf);
    *out_bytes = bytes;
    return 0;
}

/* sync open + uring read */
static int read_iouring(struct dataset *ds, uint64_t *out_bytes) {
    struct io_uring ring;
    int ret = io_uring_queue_init(QD, &ring, 0);
    if (ret < 0) {
        fprintf(stderr, "io_uring_queue_init: %s\n", strerror(-ret));
        return -1;
    }

    unsigned char **bufs = calloc((size_t)QD, sizeof(*bufs));
    int *fds = calloc((size_t)QD, sizeof(*fds));
    off_t *left = calloc((size_t)QD, sizeof(*left));
    int *fidx = calloc((size_t)QD, sizeof(*fidx));
    if (!bufs || !fds || !left || !fidx) { ret = -1; goto out; }
    for (int i = 0; i < QD; i++) {
        bufs[i] = malloc(BUF_CAP);
        if (!bufs[i]) { ret = -1; goto out; }
        fds[i] = -1;
    }

    uint64_t bytes = 0;
    int next = 0, inflight = 0, done_files = 0;

    while (done_files < ds->n || inflight > 0) {
        while (inflight < QD && next < ds->n) {
            int slot = -1;
            for (int s = 0; s < QD; s++) if (fds[s] < 0) { slot = s; break; }
            if (slot < 0) break;
            int fd = open(ds->files[next].path, O_RDONLY);
            if (fd < 0) { ret = -1; goto out; }
            fds[slot] = fd;
            left[slot] = ds->files[next].size;
            fidx[slot] = next;
            next++;
            if (left[slot] == 0) {
                close(fd); fds[slot] = -1; done_files++; continue;
            }
            size_t chunk = (size_t)((left[slot] > BUF_CAP) ? BUF_CAP : left[slot]);
            struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
            if (!sqe) break;
            io_uring_prep_read(sqe, fd, bufs[slot], chunk, 0);
            io_uring_sqe_set_data64(sqe, (uint64_t)slot);
            inflight++;
        }
        if (inflight == 0) break;
        io_uring_submit(&ring);
        struct io_uring_cqe *cqe;
        ret = io_uring_wait_cqe(&ring, &cqe);
        if (ret < 0) goto out;
        int slot = (int)io_uring_cqe_get_data64(cqe);
        if (cqe->res < 0) {
            fprintf(stderr, "cqe error: %s\n", strerror(-cqe->res));
            io_uring_cqe_seen(&ring, cqe); ret = -1; goto out;
        }
        ssize_t n = cqe->res;
        io_uring_cqe_seen(&ring, cqe);
        inflight--;
        bytes += (uint64_t)n;
        left[slot] -= n;
        if (left[slot] > 0) {
            size_t chunk = (size_t)((left[slot] > BUF_CAP) ? BUF_CAP : left[slot]);
            off_t off = ds->files[fidx[slot]].size - left[slot];
            struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
            io_uring_prep_read(sqe, fds[slot], bufs[slot], chunk, off);
            io_uring_sqe_set_data64(sqe, (uint64_t)slot);
            inflight++;
            io_uring_submit(&ring);
        } else {
            close(fds[slot]); fds[slot] = -1; done_files++;
        }
    }
    *out_bytes = bytes;
    ret = 0;
out:
    if (fds) for (int i = 0; i < QD; i++) if (fds[i] >= 0) close(fds[i]);
    if (bufs) for (int i = 0; i < QD; i++) free(bufs[i]);
    free(bufs); free(fds); free(left); free(fidx);
    io_uring_queue_exit(&ring);
    return ret;
}

/*
 * For each file: SQE openat -> linked SQE read (full file if size <= BUF_CAP).
 * Files larger than BUF_CAP fall back to multi-read after open completes.
 * Encoded user_data: (slot<<2) | phase  where phase 0=open,1=read,2=close
 */
enum { PH_OPEN = 0, PH_READ = 1, PH_CLOSE = 2 };

static int read_iouring_openat(struct dataset *ds, uint64_t *out_bytes) {
    struct io_uring ring;
    int ret = io_uring_queue_init(QD * 2, &ring, 0);
    if (ret < 0) {
        fprintf(stderr, "io_uring_queue_init: %s\n", strerror(-ret));
        return -1;
    }

    unsigned char **bufs = calloc((size_t)QD, sizeof(*bufs));
    int *fds = calloc((size_t)QD, sizeof(*fds));
    off_t *left = calloc((size_t)QD, sizeof(*left));
    int *fidx = calloc((size_t)QD, sizeof(*fidx));
    int *busy = calloc((size_t)QD, sizeof(*busy));
    if (!bufs || !fds || !left || !fidx || !busy) { ret = -1; goto out; }
    for (int i = 0; i < QD; i++) {
        /* per-slot buffer: max(BUF_CAP, we'll chunk) */
        bufs[i] = malloc(BUF_CAP);
        if (!bufs[i]) { ret = -1; goto out; }
        fds[i] = -1;
    }

    uint64_t bytes = 0;
    int next = 0, inflight = 0, done_files = 0;

    while (done_files < ds->n || inflight > 0) {
        while (inflight < QD && next < ds->n) {
            int slot = -1;
            for (int s = 0; s < QD; s++) if (!busy[s]) { slot = s; break; }
            if (slot < 0) break;
            busy[slot] = 1;
            fidx[slot] = next;
            left[slot] = ds->files[next].size;
            next++;

            struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
            if (!sqe) { busy[slot] = 0; next--; break; }
            io_uring_prep_openat(sqe, AT_FDCWD, ds->files[fidx[slot]].path, O_RDONLY, 0);
            io_uring_sqe_set_data64(sqe, ((uint64_t)slot << 2) | PH_OPEN);
            inflight++;
        }
        if (inflight == 0) break;
        io_uring_submit(&ring);

        struct io_uring_cqe *cqe;
        ret = io_uring_wait_cqe(&ring, &cqe);
        if (ret < 0) goto out;
        uint64_t ud = io_uring_cqe_get_data64(cqe);
        int slot = (int)(ud >> 2);
        int phase = (int)(ud & 3);
        int res = cqe->res;
        io_uring_cqe_seen(&ring, cqe);
        inflight--;

        if (res < 0) {
            fprintf(stderr, "cqe phase=%d: %s\n", phase, strerror(-res));
            ret = -1; goto out;
        }

        if (phase == PH_OPEN) {
            fds[slot] = res;
            if (left[slot] == 0) {
                struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
                io_uring_prep_close(sqe, fds[slot]);
                io_uring_sqe_set_data64(sqe, ((uint64_t)slot << 2) | PH_CLOSE);
                inflight++;
                io_uring_submit(&ring);
                continue;
            }
            size_t chunk = (size_t)((left[slot] > BUF_CAP) ? BUF_CAP : left[slot]);
            struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
            io_uring_prep_read(sqe, fds[slot], bufs[slot], chunk, 0);
            io_uring_sqe_set_data64(sqe, ((uint64_t)slot << 2) | PH_READ);
            inflight++;
            io_uring_submit(&ring);
        } else if (phase == PH_READ) {
            bytes += (uint64_t)res;
            left[slot] -= res;
            if (left[slot] > 0) {
                size_t chunk = (size_t)((left[slot] > BUF_CAP) ? BUF_CAP : left[slot]);
                off_t off = ds->files[fidx[slot]].size - left[slot];
                struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
                io_uring_prep_read(sqe, fds[slot], bufs[slot], chunk, off);
                io_uring_sqe_set_data64(sqe, ((uint64_t)slot << 2) | PH_READ);
                inflight++;
                io_uring_submit(&ring);
            } else {
                struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
                io_uring_prep_close(sqe, fds[slot]);
                io_uring_sqe_set_data64(sqe, ((uint64_t)slot << 2) | PH_CLOSE);
                inflight++;
                io_uring_submit(&ring);
            }
        } else { /* PH_CLOSE */
            fds[slot] = -1;
            busy[slot] = 0;
            done_files++;
        }
    }

    *out_bytes = bytes;
    ret = 0;
out:
    if (fds) for (int i = 0; i < QD; i++) if (fds[i] >= 0) close(fds[i]);
    if (bufs) for (int i = 0; i < QD; i++) free(bufs[i]);
    free(bufs); free(fds); free(left); free(fidx); free(busy);
    io_uring_queue_exit(&ring);
    return ret;
}

struct result {
    const char *backend;
    const char *subset;
    double sec;
    uint64_t bytes;
    int nfiles;
};

static int run_one(const char *backend, struct dataset *ds, const char *subset, struct result *r) {
    uint64_t bytes = 0;
    double t0 = now_s();
    int rc;
    if (strcmp(backend, "posix") == 0) rc = read_posix(ds, &bytes);
    else if (strcmp(backend, "iouring") == 0) rc = read_iouring(ds, &bytes);
    else if (strcmp(backend, "iouring_openat") == 0) rc = read_iouring_openat(ds, &bytes);
    else return -1;
    double t1 = now_s();
    if (rc != 0) return rc;
    r->backend = backend;
    r->subset = subset;
    r->sec = t1 - t0;
    r->bytes = bytes;
    r->nfiles = ds->n;
    return 0;
}

static void filter_subset(struct dataset *all, struct dataset *out, int small) {
    out->n = 0;
    out->total_bytes = 0;
    const off_t lim = 256 * 1024;
    for (int i = 0; i < all->n; i++) {
        int is_small = all->files[i].size < lim;
        if ((small && is_small) || (!small && !is_small)) {
            out->files[out->n] = all->files[i];
            out->total_bytes += (uint64_t)all->files[i].size;
            out->n++;
        }
    }
}

static void print_json_result(struct result *r) {
    double mib = (double)r->bytes / (1024.0 * 1024.0);
    double mibs = r->sec > 0 ? mib / r->sec : 0;
    printf("{\"backend\":\"%s\",\"subset\":\"%s\",\"nfiles\":%d,\"bytes\":%llu,"
           "\"sec\":%.6f,\"MiB\":%.3f,\"MiB_s\":%.3f}\n",
           r->backend, r->subset, r->nfiles,
           (unsigned long long)r->bytes, r->sec, mib, mibs);
}

static void usage(const char *argv0) {
    fprintf(stderr,
            "Usage: %s --root DIR [--mode all|small|large|mixed] "
            "[--backend all|posix|iouring|iouring_openat] [--repeat N]\n",
            argv0);
}

int main(int argc, char **argv) {
    const char *root = NULL;
    const char *mode = "all";
    const char *backend = "all";
    int repeat = 3;

    static struct option opts[] = {
        {"root", required_argument, 0, 'r'},
        {"mode", required_argument, 0, 'm'},
        {"backend", required_argument, 0, 'b'},
        {"repeat", required_argument, 0, 'n'},
        {"help", no_argument, 0, 'h'},
        {0, 0, 0, 0},
    };
    int c;
    while ((c = getopt_long(argc, argv, "r:m:b:n:h", opts, NULL)) != -1) {
        if (c == 'r') root = optarg;
        else if (c == 'm') mode = optarg;
        else if (c == 'b') backend = optarg;
        else if (c == 'n') repeat = atoi(optarg);
        else { usage(argv[0]); return 2; }
    }
    if (!root) { usage(argv[0]); return 2; }

    struct dataset all = {0};
    all.files = calloc(MAX_FILES, sizeof(*all.files));
    walk_dir(&all, root);
    if (all.n == 0) {
        fprintf(stderr, "no files under %s — run scripts/gen_dataset.sh\n", root);
        return 1;
    }
    fprintf(stderr, "dataset: %d files, %.2f MiB under %s\n",
            all.n, (double)all.total_bytes / (1024.0 * 1024.0), root);

    struct dataset small = {0}, large = {0}, mixed = all;
    small.files = calloc(MAX_FILES, sizeof(*small.files));
    large.files = calloc(MAX_FILES, sizeof(*large.files));
    filter_subset(&all, &small, 1);
    filter_subset(&all, &large, 0);

    const char *backends[] = {"posix", "iouring", "iouring_openat", NULL};
    struct dataset *sets[4];
    const char *names[4];
    int nsets = 0;
    if (strcmp(mode, "all") == 0 || strcmp(mode, "small") == 0) {
        sets[nsets] = &small; names[nsets] = "small_files"; nsets++;
    }
    if (strcmp(mode, "all") == 0 || strcmp(mode, "large") == 0) {
        sets[nsets] = &large; names[nsets] = "large_files"; nsets++;
    }
    if (strcmp(mode, "all") == 0 || strcmp(mode, "mixed") == 0) {
        sets[nsets] = &mixed; names[nsets] = "mixed"; nsets++;
    }

    for (int bi = 0; backends[bi]; bi++) {
        if (strcmp(backend, "all") != 0 && strcmp(backend, backends[bi]) != 0) continue;
        for (int si = 0; si < nsets; si++) {
            if (sets[si]->n == 0) continue;
            struct result discard;
            if (run_one(backends[bi], sets[si], names[si], &discard) != 0) {
                fprintf(stderr, "FAIL warm %s %s\n", backends[bi], names[si]);
                return 1;
            }
            for (int r = 0; r < repeat; r++) {
                struct result res;
                if (run_one(backends[bi], sets[si], names[si], &res) != 0) {
                    fprintf(stderr, "FAIL %s %s\n", backends[bi], names[si]);
                    return 1;
                }
                print_json_result(&res);
                fflush(stdout);
            }
        }
    }

    free(all.files);
    free(small.files);
    free(large.files);
    return 0;
}
