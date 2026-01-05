#!/usr/bin/env python3
"""Healthcheck script for Docker container.

Checks that last_successful_run is within expected interval based on cron schedule.
Exit code 0 = healthy, 1 = unhealthy.
"""

import os
import sys
from datetime import datetime, timedelta

from cronsim import CronSim

from letterboxd_trakt.config import load_config


def get_expected_interval(cron_schedule: str) -> timedelta:
    """Calculate expected interval between runs based on cron schedule.
    
    Returns the interval plus 50% margin for safety.
    """
    now = datetime.now()
    cron = CronSim(cron_schedule, now)
    
    # Get next two runs to calculate interval
    next_run = next(cron)
    second_run = next(cron)
    
    interval = second_run - next_run
    # Add 50% margin
    return interval * 1.5


def main():
    config = load_config()
    
    if not config:
        print("UNHEALTHY: Cannot load config")
        sys.exit(1)
    
    if not config.last_successful_run:
        # No successful run yet - could be first startup
        # Consider healthy if container just started
        print("WARNING: No successful run recorded yet")
        sys.exit(0)
    
    cron_schedule = os.getenv("CRON_SCHEDULE", "0 * * * *")
    expected_interval = get_expected_interval(cron_schedule)
    
    time_since_last_run = datetime.now() - config.last_successful_run
    
    if time_since_last_run > expected_interval:
        print(f"UNHEALTHY: Last run was {time_since_last_run} ago (expected < {expected_interval})")
        sys.exit(1)
    
    print(f"HEALTHY: Last run {time_since_last_run} ago")
    sys.exit(0)


if __name__ == "__main__":
    main()

