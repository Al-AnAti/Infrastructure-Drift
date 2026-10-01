from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class ServiceSpec:
    name: str
    image: str
    ports: dict[str, str]
    labels: dict[str, str]


def parse_compose_file(filepath: Path):
    with open(filepath , 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    services = []
    for name, specs in data['services'].items():
        ports = {}
        for port in specs['ports']:
            hport, dport = port.split(':')
            if "udp" not in dport:
                dport += "/tcp"
            ports[dport] = hport

        labels = {}
        for label in specs['labels']:
            k, v = label.split('=', 1)
            labels[k] = v

        s = ServiceSpec(name, specs['image'], ports, labels)
        services.append(s)

    return services
