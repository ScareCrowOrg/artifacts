"""
GateKeeperMetrics – Prometheus-compatible metrics collection.

Tracks:
- Venv creation time (histogram) and venv size per worker.
- Job execution time per job-type.
- Job success / failure counts per job-type.

Provides:
- In-memory aggregation via Python dicts.
- ``get_summary()`` for structured dict output (logging, health-check endpoints).
- ``prometheus_export()`` for Prometheus text-format scraping.
"""

import time
from typing import Dict, List


class GateKeeperMetrics:
    """
    Collect and export metrics for GateKeeper venv management and job execution.

    All state is held in plain Python dicts / lists; no external libraries
    are required.  For production Prometheus integration, the
    ``prometheus_export()`` string can be served from a ``/metrics`` endpoint.
    """

    def __init__(self) -> None:
        # Venv metrics
        self.venv_creation_times: Dict[str, List[float]] = {}   # worker → [seconds]
        self.venv_sizes_mb: Dict[str, List[float]] = {}          # worker → [MB]
        self.venv_rebuild_counts: Dict[str, int] = {}            # worker → count

        # Job metrics
        self.job_execution_times: Dict[str, List[float]] = {}   # job_type → [seconds]
        self.job_successes: Dict[str, int] = {}                  # job_type → count
        self.job_failures: Dict[str, int] = {}                   # job_type → count
        self.job_backpressure: Dict[str, int] = {}               # job_type → count (resource contention)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_venv_creation(
        self,
        worker_name: str,
        creation_time_sec: float,
        size_mb: float,
    ) -> None:
        """Record venv creation time and size for *worker_name*."""
        if worker_name not in self.venv_creation_times:
            self.venv_creation_times[worker_name] = []
            self.venv_sizes_mb[worker_name] = []

        self.venv_creation_times[worker_name].append(creation_time_sec)
        self.venv_sizes_mb[worker_name].append(size_mb)

    def record_venv_rebuild(self, worker_name: str) -> None:
        """Increment the rebuild counter for *worker_name*."""
        self.venv_rebuild_counts[worker_name] = (
            self.venv_rebuild_counts.get(worker_name, 0) + 1
        )

    def record_job_backpressure(self, job_type: str) -> None:
        """Increment the backpressure (resource contention) counter for *job_type*."""
        self.job_backpressure[job_type] = self.job_backpressure.get(job_type, 0) + 1

    def record_job_execution(
        self,
        job_type: str,
        execution_time_sec: float,
        success: bool,
    ) -> None:
        """Record job execution time and outcome for *job_type*."""
        if job_type not in self.job_execution_times:
            self.job_execution_times[job_type] = []
            self.job_successes[job_type] = 0
            self.job_failures[job_type] = 0

        self.job_execution_times[job_type].append(execution_time_sec)
        if success:
            self.job_successes[job_type] += 1
        else:
            self.job_failures[job_type] += 1

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def get_summary(self) -> dict:
        """Return a structured metrics summary suitable for JSON logging."""
        venv_stats: dict = {}
        for worker, times in self.venv_creation_times.items():
            sizes = self.venv_sizes_mb.get(worker, [])
            venv_stats[worker] = {
                "creation_count": len(times),
                "avg_creation_sec": _avg(times),
                "min_creation_sec": min(times) if times else 0.0,
                "max_creation_sec": max(times) if times else 0.0,
                "avg_size_mb": _avg(sizes),
                "rebuild_count": self.venv_rebuild_counts.get(worker, 0),
            }

        all_job_types = set(
            list(self.job_successes.keys()) + list(self.job_failures.keys())
        )
        job_stats: dict = {}
        for job_type in sorted(all_job_types):
            times = self.job_execution_times.get(job_type, [])
            job_stats[job_type] = {
                "successes": self.job_successes.get(job_type, 0),
                "failures": self.job_failures.get(job_type, 0),
                "backpressure": self.job_backpressure.get(job_type, 0),
                "avg_exec_time_sec": _avg(times),
                "min_exec_time_sec": min(times) if times else 0.0,
                "max_exec_time_sec": max(times) if times else 0.0,
            }

        return {"venv_stats": venv_stats, "job_stats": job_stats}

    def prometheus_export(self) -> str:
        """
        Serialise all metrics in Prometheus text format.

        Returns:
            Multi-line string ready to serve from a ``/metrics`` endpoint.
        """
        lines: List[str] = []

        # --- Venv metrics ---
        lines.append("# HELP venv_creation_time_seconds Time to create a worker venv")
        lines.append("# TYPE venv_creation_time_seconds gauge")
        for worker, times in self.venv_creation_times.items():
            if times:
                avg = _avg(times)
                lines.append(
                    f'venv_creation_time_seconds{{worker="{worker}"}} {avg:.4f}'
                )

        lines.append("# HELP venv_creation_count Total venv creations per worker")
        lines.append("# TYPE venv_creation_count counter")
        for worker, times in self.venv_creation_times.items():
            lines.append(
                f'venv_creation_count{{worker="{worker}"}} {len(times)}'
            )

        lines.append("# HELP venv_size_mb Average venv disk size in megabytes")
        lines.append("# TYPE venv_size_mb gauge")
        for worker, sizes in self.venv_sizes_mb.items():
            if sizes:
                lines.append(
                    f'venv_size_mb{{worker="{worker}"}} {_avg(sizes):.2f}'
                )

        lines.append("# HELP venv_rebuild_count Total venv rebuilds per worker")
        lines.append("# TYPE venv_rebuild_count counter")
        for worker, count in self.venv_rebuild_counts.items():
            lines.append(f'venv_rebuild_count{{worker="{worker}"}} {count}')

        # --- Job metrics ---
        lines.append("# HELP job_successes_total Total successful jobs per job_type")
        lines.append("# TYPE job_successes_total counter")
        for job_type, count in self.job_successes.items():
            lines.append(f'job_successes_total{{job_type="{job_type}"}} {count}')

        lines.append("# HELP job_failures_total Total failed jobs per job_type")
        lines.append("# TYPE job_failures_total counter")
        for job_type, count in self.job_failures.items():
            lines.append(f'job_failures_total{{job_type="{job_type}"}} {count}')

        lines.append(
            "# HELP job_backpressure_total Total job backpressure events per job_type"
        )
        lines.append("# TYPE job_backpressure_total counter")
        for job_type, count in self.job_backpressure.items():
            lines.append(f'job_backpressure_total{{job_type="{job_type}"}} {count}')

        lines.append(
            "# HELP job_execution_time_seconds Average job execution time per job_type"
        )
        lines.append("# TYPE job_execution_time_seconds gauge")
        for job_type, times in self.job_execution_times.items():
            if times:
                lines.append(
                    f'job_execution_time_seconds{{job_type="{job_type}"}} {_avg(times):.4f}'
                )

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _avg(values: List[float]) -> float:
    """Return the arithmetic mean of *values*, or 0.0 if the list is empty."""
    return sum(values) / len(values) if values else 0.0
