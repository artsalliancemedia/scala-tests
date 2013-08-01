## Scala tools

Creates a new playlist in Scala consisting of an item "test_image.png", puts the playlist into a schedule and updates the player to sync the new changes.

### Installation

Python 2.6.x is required
Just clone the repo, all requirements are included (see below)

### Next Steps

Take a copy of `settings-template.json`, name it `settings.json` and fill out the fields.

By default, the application will use this `settings.json` file.

To start the app run:
`python scala-tools.py`

### Included libraries

This includes the following libraries from Scala. They are not provided via pip that is why they are directly in the repo.

## Scalalib

A set of modules with tools and utilities for common needs at playback
time, communication, synchronization, publishing, Player provisioning, etc.


#### Scws

Webservice modules for communicating with Content Manager 5 in a simple
manner.  Example command-line upload to CM included.
