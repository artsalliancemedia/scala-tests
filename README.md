## Scala tests

#### Scala Tools
Creates a new playlist in Scala consisting of an item "test_image.png", puts the playlist into a schedule and updates the player to sync the new changes.

#### Scala Monitor
Provides a class to monitor a chosen player, and report back a variety of information on that player such as files it uses and screen layouts.

### Installation

Python 2.6.x is required
Just clone the repo, all requirements are included (see below)

### Next Steps

Take a copy of `settings-template.json`, name it `settings.json` and fill out the fields.

By default, the application will use this `settings.json` file.

To start the scala test app run:
`python scala_tools.py`

To start the monitoring app run:
`python scala_monitor.py`

### Included libraries

This includes the following libraries from Scala. They are not provided via pip that is why they are directly in the repo.

## Scalalib

A set of modules with tools and utilities for common needs at playback
time, communication, synchronization, publishing, Player provisioning, etc.


#### Scws

Webservice modules for communicating with Content Manager 5 in a simple
manner.  Example command-line upload to CM included.


## Creating your own code for interacting with python

#### Initial steps

Clone this repo, or by other means copy the scws module.

    from webservices.scws import scws

    baseurl = "http://my-scala-box:8080/ContentManager/"
    authstr = "username:password"
    api = "v1.2"
    content_manager = scws.ConManager(baseurl, authstr, api_vers=api)

#### Simple use cases

Now the Content Manager is connected, you can usue the `content_manager` object to access a variety of functions. For example, to list the names of all players:

    players = content_manager.PlayerRS.list()
    for player in players:
        print player.name

The Content Manager API can be found at [the Scala developer wiki](https://developer.scala.com/dev/index.php/API_version_main), although take care not to
try to call functions from version 1.3.

The API calls typically take in an ID of an object to find, and typically return an array of relevant objects. More complex search functions can often take a SearchCritera object.
For example, to search for all channels with names containing "test":

    channel_filter = scws.TObj()
    channel_filter.column       = u'name'
    channel_filter.restriction  = u'LIKE'
    channel_filter.value        = u'%test%'
    test_channels = content_manager.ChannelRS.list(searchCriteria=channel_filter)


#### MetaValues
Players, Messages and Media items can contain meta-values, which are accessed differently to the main objects, using `MediaRS.getMetaValues(mediaId=id)` for example.

### Layout
The basic structure of a Scala player is as follows. The Content Manager will have links to a variety of `Player`s. A `Player` contains a number of `Display`s, which each contains a single `Channel`. A `Channel` has a `Schedule` and a `Frameset`. The `Frameset` contains multiple `Frame`s, and dictates how the frames are laid out, any bezel sizes, the ordering of frames from front to back, and so on. The `Schedule` dictates at what times a `Playlist` is shown, and on which `Frame`s. A `Playlist` can contain `Media`, `Audio`, or `Data`, and specifies ordering, transitions, lengths images are displayed for, and so on and so forth.


