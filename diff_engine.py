from dataclasses import dataclass

from yaml_parser import ServiceSpec, parse_compose_file


@dataclass
class DriftReport:
    # List of container names running in Docker but missing from Git
    rogue_containers: list[ServiceSpec] 
    
    # Dictionary mapping container names to a list of specific mismatches 
    # e.g. {"web": ["Port mismatch: expected 8081, got 8080"]}
    config_drifts: dict[str, tuple[ServiceSpec, list[str]]] 
    
    def is_healthy(self) -> bool:
        return len(self.rogue_containers) == 0 and len(self.config_drifts) == 0


def compute_drift(git_specs: list[ServiceSpec], docker_specs: list[ServiceSpec]) -> DriftReport:
    report = DriftReport(rogue_containers=[], config_drifts={})
    
    # 1. Setup O(1) lookup dictionaries
    docker_dict = {s.name: s for s in docker_specs}
    git_dict = {s.name: s for s in git_specs}
    
    # 2. Find Rogue Containers
    rogue_names = set(docker_dict.keys()) - set(git_dict.keys())
    report.rogue_containers = [service for name, service in docker_dict.items() if name in rogue_names]
    
    # 3. Check for Config Drift and Missing Containers
    for name, git_spec in git_dict.items():
        if name not in docker_dict:
            report.config_drifts[name] = (git_spec, ["Container is missing/not running"])
            continue
            
        docker_spec = docker_dict[name]
        drifts = []

        # Image mismatch check:
        if git_spec.image != docker_dict[name].image:
            drifts.append(f"Image mismatch: expected: [{git_spec.image}], got: [{docker_dict[name].image}]")

        for git_dport, git_hport in git_spec.ports.items():
            docker_hport = docker_dict[name].ports.get(git_dport, None)
            if docker_hport is None:
                drifts.append(f"Ports mismatch: expected: [{git_hport}:{git_dport}], but docker port was not found!")
            elif git_hport != docker_hport:
                drifts.append(f"Ports mismatch: expected: [{git_hport}:{git_dport}], got: [{docker_hport}:{git_dport}]")
        
        # Labels mismatch check:
        for git_k, git_v in git_spec.labels.items():
            docker_v = docker_dict[name].labels.get(git_k, None)
            if docker_v is None:
                drifts.append(f"Labels mismatch: expected: [{git_k}={git_v}], but label was not found!")
            elif git_v != docker_v:
                drifts.append(f"Labels mismatch: expected: [{git_k}={git_v}], got: [{git_k}={docker_v}]")

        if drifts:
            report.config_drifts[name] = (docker_spec, drifts)
            
    return report
