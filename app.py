import os
import time
from datetime import datetime, timezone


def main() -> None:
    app_name = os.getenv("APP_NAME", "rofl-mining")
    wallet = os.getenv("MINING_WALLET", "not-configured")
    pool = os.getenv("MINING_POOL", "not-configured")

    while True:
        now = datetime.now(timezone.utc).isoformat()
        print(
            f"{now} {app_name} is running in ROFL-ready container. "
            f"wallet={wallet} pool={pool}",
            flush=True,
        )
        time.sleep(60)


if __name__ == "__main__":
    main()
