# rofl-mining

Minimal Oasis ROFL container project.

## Local checks

```powershell
docker compose build
docker compose up
```

## ROFL flow

```powershell
oasis rofl create --network testnet
oasis rofl build
oasis rofl update
oasis rofl deploy
oasis rofl machine show
oasis rofl machine logs
```

Before deploying, configure:

- GitHub repository remote URL.
- Container image name in `compose.yaml`.
- Oasis wallet account with testnet or mainnet ROSE.
- Real mining command, wallet address, and pool endpoint if this project should run an actual miner.
