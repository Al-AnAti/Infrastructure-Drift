from pathlib import Path
import sys

from yaml_parser import parse_compose_file
from docker_watcher import DockerWatcher
from diff_engine import compute_drift
from reconciler import Reconciler


COMPOSE_FILE = Path(__file__).resolve().parent / "docker-compose.test.yaml"


def display_report(report):
    if not report.rogue_containers and not report.config_drifts:
        print("\n✅ State is fully reconciled. No drifts detected.")
        return False

    print("\n⚠️  DRIFT DETECTED ⚠️")
    print("=" * 40)
    
    if report.rogue_containers:
        print(f"\n👽 Rogue Containers ({len(report.rogue_containers)}):")
        for container in report.rogue_containers:
            print(f"  + {container.name} (Image: {container.image})")

    if report.config_drifts:
        print(f"\n⚙️  Config Drifts ({len(report.config_drifts)}):")
        for name, (spec, drifts) in report.config_drifts.items():
            print(f"  ~ {name}:")
            for drift in drifts:
                print(f"      - {drift}")
                
    print("\n" + "=" * 40)
    return True


def main():
    print("🔍 Inspecting GitOps state...")
    
    # 1. Gather State
    git_specs = parse_compose_file(COMPOSE_FILE)
    docker_specs = DockerWatcher().get_snapshot()
    
    # 2. Compute Drift
    report = compute_drift(git_specs=git_specs, docker_specs=docker_specs)
    
    # 3. Display Drift
    has_drift = display_report(report)
    if not has_drift:
        sys.exit(0)

    # 4. Prompt User
    print("\nOptions:")
    print("  [1] 📥 Adopt   (Write rogue containers into compose file)")
    print("  [2] 🔨 Enforce (Destroy rogues, recreate drifted containers)")
    print("  [3] 🛑 Ignore  (Exit without changes)")
    
    choice = input("\nSelect an action (1/2/3): ").strip()
    
    # 5. Execute Action
    reconciler = Reconciler(filepath=COMPOSE_FILE)
    
    if choice == '1':
        print("\n📥 Adopting rogue containers...")
        reconciler.adopt_state(report)
        print("✅ Adopt complete! Check your docker-compose.test.yaml.")
        
    elif choice == '2':
        print("\n🔨 Enforcing state...")
        reconciler.enforce_state(report)
        print("✅ Enforce complete!")
        
    else:
        print("\n🛑 Exiting. No changes made.")


if __name__ == "__main__":
    main()
