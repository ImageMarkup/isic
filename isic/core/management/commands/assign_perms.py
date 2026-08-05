import time

import djclick as click

from isic.core.guardian_permissions import initialize_guardian_permissions


@click.command(help="Assign permissions to existing objects")
def assign_permissions():
    start = time.perf_counter()
    initialize_guardian_permissions()
    end = time.perf_counter()
    click.secho(f"Permission assignment completed in {end - start} seconds.", fg="green")
