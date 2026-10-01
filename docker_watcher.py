import docker

from yaml_parser import ServiceSpec


class DockerWatcher:
    def __init__(self):
        self.client = docker.from_env()
        self.managed_label = "sentinel.managed=true"


    def get_snapshot(self) -> list[ServiceSpec]:
        """Takes a point-in-time snapshot of all running containers matching our label.""" 
        snapshot = []
        containers = self.client.containers.list()
        
        for container in containers:
            ports = {}
            for dport, info in container.ports.items():
                if info:
                    hport = info[0]['HostPort']
                    ports[dport] = hport

            labels = {}
            for k, v in container.labels.items():
                if k.startswith("sentinel."):
                    labels[k] = v
                    
            s = ServiceSpec(
                name = container.labels.get("com.docker.compose.service", container.name), 
                image = container.attrs["Config"]["Image"],
                ports = ports, 
                labels = labels
            )
            snapshot.append(s)

        return snapshot


    def listen_to_events(self):
        event_stream = self.client.events(
            decode=True,
            filters={
                "type": "container",
                "event": ["start", "die"]
            }
        )

        for event in event_stream:
            yield event
