# Infrastructure Drift

Infrastructure Drift compares the services declared in `docker-compose.test.yaml` with the containers currently running in Docker. When it finds a difference, it reports the drift and lets you adopt the running state, enforce the Compose configuration, or exit without making changes.

I built it to explore a small GitOps-style reconciliation loop: keep a configuration file as the desired state, inspect the running state, compare the two, and choose how to respond when they differ.

## How it works

`main.py` coordinates the run:

1. `yaml_parser.py` reads the Compose file and converts each service into a `ServiceSpec` containing its name, image, ports, and labels. Ports are represented as container-port-to-host-port mappings, with `/tcp` added when no protocol is specified.
2. `docker_watcher.py` uses the Docker SDK to take a snapshot of running containers. It uses the Compose service label as the service name when available, otherwise it uses the container name. It reads the configured image, published ports, and labels beginning with `sentinel.`.
3. `diff_engine.py` matches services by name and reports running containers that have no matching Compose service, Compose services that are not running, and mismatches in image, declared ports, or declared labels.
4. `main.py` prints the report and offers three actions:
	- **Adopt** writes rogue containers into the Compose file and updates drifted services to match their running container configuration. A service that is declared but missing from Docker is removed from the Compose file.
	- **Enforce** stops and removes rogue and drifted containers, then runs `docker-compose up -d` for each drifted service so Compose can recreate it from the file. Missing services are included in this recreation step.
	- **Ignore** exits without changes.

`reconciler.py` handles those changes. When adopting, it uses `ruamel.yaml` to preserve YAML formatting and quotes while rewriting the file.

The comparison is intentionally limited to image, declared ports, and declared labels. It does not compare every Compose setting, and it checks expected ports and labels rather than reporting extra ones. The watcher examines all running containers; the `sentinel.*` label prefix filters which labels it records, not which containers it sees. As a result, unrelated running containers can be reported as rogue.

## Technologies

- Python
- Docker SDK for Python (`docker`)
- PyYAML (`yaml`) for reading Compose configuration
- `ruamel.yaml` for writing updated configuration while preserving formatting
- Docker Engine and Docker Compose

## Setup and usage

You need Python 3, a running Docker Engine that the Docker SDK can access, and Docker Compose. Enforce uses the `docker-compose` command, so that executable must be available on your `PATH` for that action.

Install the Python dependencies:

```sh
python -m pip install docker PyYAML ruamel.yaml
```

Start the example services and run the checker:

```sh
docker compose -f docker-compose.test.yaml up -d
python main.py
```

To create a rogue container and see it reported, run the following before `python main.py`:

```sh
docker run -d --name rogue-postgres -e POSTGRES_PASSWORD=secret postgres:14-alpine
```

The checker will include all running containers in its snapshot, so use this example in a Docker environment where you are comfortable with other running containers potentially being listed as rogue. Clean up the example and Compose services with:

```sh
docker rm -f rogue-postgres
docker compose -f docker-compose.test.yaml down
```