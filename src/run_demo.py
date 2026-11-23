"""Demo walkthrough: two orgs, one project, the worker, and the feed."""

from src.tenancy import Tenancy
from src.worker import Worker


def main() -> None:
    tenancy = Tenancy()
    worker = Worker(tenancy)

    tenancy.create_organization("acme", "Acme Corp")
    tenancy.create_organization("globex", "Globex Inc")
    tenancy.add_user("u-ana", "ana@example.com")
    tenancy.add_member("u-ana", "acme")

    acme = tenancy.for_organization("acme")
    globex = tenancy.for_organization("globex")

    project_id = acme.add_project("Website redesign")
    worker.enqueue("acme", {"kind": "project-created", "name": "Website redesign"})
    print(f"1. Added project {project_id} to Acme; it shows up right away:")
    print(f"   Acme projects: {acme.list_projects()}")
    print(f"   Globex projects: {globex.list_projects()} (separate schema)")
    print(f"   Pending events: {worker.pending_count()}")

    processed = worker.run_once()
    print(f"\n2. Worker ran, processed {processed} event(s)")
    print(f"   Acme activity: {acme.list_activity()}")
    print(f"   Globex activity: {globex.list_activity()} (nothing leaked)")
    print(f"   Pending events: {worker.pending_count()}")


if __name__ == "__main__":
    main()
