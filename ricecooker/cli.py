# -*- coding: utf-8 -*-

import click

@click.command()
def main(args=None):
    """Console script for ricecooker"""
    click.echo("Ricecooker is installed")
    click.echo("See click documentation at https://github.com/learningequality/ricecooker")


if __name__ == "__main__":
    main()
