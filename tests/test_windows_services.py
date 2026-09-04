import unittest

from mikan_pet.services.media_keys import KEYEVENTF_KEYUP, MediaAction, MediaKeyService
from mikan_pet.services.singleton import ERROR_ALREADY_EXISTS, SingleInstance


class FakeMediaBackend:
    def __init__(self) -> None:
        self.events: list[tuple[int, int]] = []

    def key_event(self, virtual_key: int, flags: int) -> None:
        self.events.append((virtual_key, flags))


class FakeMutexBackend:
    def __init__(self, last_error: int) -> None:
        self.last_error = last_error
        self.closed: list[object] = []
        self.handle = object()

    def create_mutex(self, name: str) -> object:
        return self.handle

    def get_last_error(self) -> int:
        return self.last_error

    def close_handle(self, handle: object) -> None:
        self.closed.append(handle)


class WindowsServiceTests(unittest.TestCase):
    def test_every_media_action_emits_exact_key_down_then_key_up(self) -> None:
        expected = {
            MediaAction.PREVIOUS: 0xB1,
            MediaAction.PLAY_PAUSE: 0xB3,
            MediaAction.NEXT: 0xB0,
        }
        for action, virtual_key in expected.items():
            with self.subTest(action=action):
                backend = FakeMediaBackend()
                MediaKeyService(backend).send(action)
                self.assertEqual(
                    [(virtual_key, 0), (virtual_key, KEYEVENTF_KEYUP)],
                    backend.events,
                )

    def test_duplicate_mutex_returns_false_and_closes_handle(self) -> None:
        backend = FakeMutexBackend(ERROR_ALREADY_EXISTS)
        guard = SingleInstance("Local\\MikanPet", backend)
        self.assertFalse(guard.acquire())
        self.assertEqual([backend.handle], backend.closed)

    def test_owned_mutex_is_released_once(self) -> None:
        backend = FakeMutexBackend(0)
        guard = SingleInstance("Local\\MikanPet", backend)
        self.assertTrue(guard.acquire())
        guard.release()
        guard.release()
        self.assertEqual([backend.handle], backend.closed)

    def test_context_manager_releases_owned_mutex(self) -> None:
        backend = FakeMutexBackend(0)
        with SingleInstance("Local\\MikanPet", backend) as guard:
            self.assertTrue(guard.acquired)
        self.assertEqual([backend.handle], backend.closed)

    def test_repeated_acquire_does_not_create_or_close_twice(self) -> None:
        backend = FakeMutexBackend(0)
        guard = SingleInstance("Local\\MikanPet", backend)
        self.assertTrue(guard.acquire())
        self.assertTrue(guard.acquire())
        guard.release()
        self.assertEqual([backend.handle], backend.closed)


if __name__ == "__main__":
    unittest.main()
