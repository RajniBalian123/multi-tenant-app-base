"""Checks for isolation, ordering, and crash safety."""

import unittest

from src.tenancy import Tenancy
from src.worker import Worker


class TestTenancy(unittest.TestCase):
    def setUp(self):
        self.tenancy = Tenancy()
        self.tenancy.create_organization("a", "Org A")
        self.tenancy.create_organization("b", "Org B")

    def test_projects_are_isolated(self):
        a = self.tenancy.for_organization("a")
        b = self.tenancy.for_organization("b")
        a.add_project("Secret Project")
        self.assertEqual([p["name"] for p in a.list_projects()],
                         ["Secret Project"])
        self.assertEqual(b.list_projects(), [])

    def test_activity_is_isolated(self):
        a = self.tenancy.for_organization("a")
        b = self.tenancy.for_organization("b")
        a.add_activity("did a thing")
        self.assertEqual(len(a.list_activity()), 1)
        self.assertEqual(b.list_activity(), [])

    def test_unknown_org_raises(self):
        with self.assertRaises(KeyError):
            self.tenancy.for_organization("nope")


class TestWorker(unittest.TestCase):
    def test_event_creates_activity(self):
        tenancy = Tenancy()
        tenancy.create_organization("a", "Org A")
        worker = Worker(tenancy)
        worker.enqueue("a", {"kind": "project-created", "name": "P1"})
        self.assertEqual(worker.pending_count(), 1)
        self.assertEqual(worker.run_once(), 1)
        self.assertEqual(worker.pending_count(), 0)
        activity = tenancy.for_organization("a").list_activity()
        self.assertEqual(len(activity), 1)
        self.assertIn("P1", activity[0]["text"])

    def test_events_survive_until_processed(self):
        # Enqueue, then create a NEW worker (as after a crash): the event
        # is still there, because it lives in the database.
        tenancy = Tenancy()
        tenancy.create_organization("a", "Org A")
        Worker(tenancy).enqueue("a", {"kind": "project-created", "name": "P1"})
        worker2 = Worker(tenancy)
        self.assertEqual(worker2.pending_count(), 1)
        worker2.run_once()
        self.assertEqual(worker2.pending_count(), 0)

    def test_activity_is_ordered(self):
        tenancy = Tenancy()
        tenancy.create_organization("a", "Org A")
        worker = Worker(tenancy)
        worker.enqueue("a", {"kind": "project-created", "name": "P1"})
        worker.enqueue("a", {"kind": "project-created", "name": "P2"})
        worker.run_once()
        activity = tenancy.for_organization("a").list_activity()
        self.assertEqual([a["seq"] for a in activity], [1, 2])
        self.assertIn("P1", activity[0]["text"])
        self.assertIn("P2", activity[1]["text"])


if __name__ == "__main__":
    unittest.main()
