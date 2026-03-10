import secrets

from faker import Faker


def pytest_addoption(parser):
    parser.addoption(
        "--faker-seed",
        type=int,
        default=None,
        help="Seed for Faker's random generator (for reproducing flaky tests).",
    )


def pytest_configure(config):
    seed = config.getoption("--faker-seed")
    if seed is None:
        seed = secrets.randbelow(2**32)
    config._faker_seed = seed  # noqa: SLF001
    Faker.seed(seed)


def pytest_report_header(config):
    seed = config._faker_seed  # noqa: SLF001
    return f"faker seed: {seed} (use --faker-seed={seed} to reproduce)"
