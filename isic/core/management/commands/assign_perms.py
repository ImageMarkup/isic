import time

import djclick as click

from isic.core.guardian_permissions import assign_image_perms, initialize_groups


@click.command(help="Assign permissions to existing objects")
def assign_permissions():
    start = time.perf_counter()
    initialize_groups()
    assign_image_perms()
    end = time.perf_counter()
    click.secho(f"Permission assignment completed in {end - start} seconds.", fg="green")
