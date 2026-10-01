from dataclasses import asdict
from pathlib import Path
import subprocess

import docker
from ruamel.yaml import YAML

from diff_engine import DriftReport


class Reconciler:
    def __init__(self, filepath: Path):
        self.client = docker.from_env()
        self.filepath = filepath


    def enforce_state(self, report: DriftReport):
        # Step 1: Destroy phase (clean up rogues and drifted containers)
        self._destroy_invalid_containers(report)

        # Step 2: Recreate phase (spin up the correct versions)
        self._recreate_drifted_containers(report)

    def _destroy_invalid_containers(self, report: DriftReport):
        rogue_names = [c.name for c in report.rogue_containers]
        containers = self.client.containers.list()
        for container in containers:
            container_name = container.labels.get("com.docker.compose.service", container.name)
            if  container_name in rogue_names or container_name in report.config_drifts:
                print(f"Stopping and removing container: {container_name}")
                container.stop()
                container.remove()
            else:
                print(f"Container {container_name} is valid. No action taken.")

    def _recreate_drifted_containers(self, report: DriftReport):
        for container_name in report.config_drifts.keys():
            subprocess.run(["docker-compose", "-f", self.filepath, "up", "-d", container_name], check=True)


    def adopt_state(self, report: DriftReport):
        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.indent(mapping=2, sequence=4, offset=2)
        
        with open(self.filepath, 'r+') as f:
            compose_data = yaml.load(f)

            # 1. Adopt Rogue Containers
            for container in report.rogue_containers:
                config = self._format_for_yaml(container)
                compose_data['services'][container.name] = config

            # 2. Adopt Config Drifts
            for name, (docker_spec, drifts) in report.config_drifts.items():
                if "Container is missing/not running" in drifts:
                    if name in compose_data['services']:
                        del compose_data['services'][name]
                        print(f"🗑️  Removed missing container [{name}] from YAML.")
                else:
                    config = self._format_for_yaml(docker_spec)
                    compose_data['services'][name] = config
                    print(f"📝 Updated drifted container [{name}] in YAML.")

            f.seek(0)
            yaml.dump(compose_data, f)
            f.truncate()

    def _format_for_yaml(self, spec) -> dict:
        """Converts ServiceSpec dictionaries back into Compose-formatted lists."""
        # Strip the name key
        config = {k: v for k, v in asdict(spec).items() if k != "name"}
        
        # 1. Format Labels (Dict -> List of "key=value")
        if not config.get('labels'):
            config.pop('labels', None)  # Remove entirely if empty
        else:
            config['labels'] = [f"{k}={v}" for k, v in config['labels'].items()]
            
        # 2. Format Ports (Dict -> List of "host:container")
        if not config.get('ports'):
            config.pop('ports', None)  # Remove entirely if empty
        else:
            ports_list = []
            for c_port, h_port in config['ports'].items():
                # Strip out the '/tcp' or '/udp' noise from Docker's port outputs
                c_port_clean = str(c_port).split('/')[0]
                ports_list.append(f"{h_port}:{c_port_clean}")
            config['ports'] = ports_list
            
        return config
