#!/usr/bin/env python
from cleo.application import Application

from subcommand.guard import GuardCommand

application = Application(name="Spot VM Init Daemon")
application.add(GuardCommand())

if __name__ == '__main__':
    application.run()
