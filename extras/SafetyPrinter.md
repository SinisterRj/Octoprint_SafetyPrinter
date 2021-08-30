---
layout: plugin

id: SafetyPrinter
title: SafetyPrinter
description: This plugin interfaces with Safety Printer MCU (https://github.com/SinisterRj/SafetyPrinter). 
authors:
- Rodrigo C. C. Silva
license: AGPLv3

date: 2021-08-30

homepage: https://github.com/SinisterRj/SafetyPrinter/wiki
source: https://github.com/SinisterRj/Octoprint_SafetyPrinter
archive: https://github.com/SinisterRj/Octoprint_SafetyPrinter/archive/refs/heads/main.zip

# TODO
# Set this to true if your plugin uses the dependency_links setup parameter to include
# library versions not yet published on PyPi. SHOULD ONLY BE USED IF THERE IS NO OTHER OPTION!
#follow_dependency_links: false

# TODO
tags:
- fire
- smoke
- notification
- bed temperature
- hotend temperature
- safety
- flame detector
- emergency
- shutdown
- trip

# TODO
screenshots:
- url: https://user-images.githubusercontent.com/81830673/131403877-08929120-4f60-4287-9d52-c4439e3d3743.PNG
  alt: Sidebar1
  caption: Sensor information sidebar in normal operation.
- url: https://user-images.githubusercontent.com/81830673/131403878-91b9ae85-5824-4c6a-8ecc-3547a118b801.PNG
  alt: Sidebar2
  caption: Sensor information sidebar in shutdown mode.
- url: https://user-images.githubusercontent.com/81830673/131403880-dc925006-be2c-4867-b86b-47fb8adfeb09.PNG
  alt: Setup
  caption: Setup options.
- url: https://user-images.githubusercontent.com/81830673/131403874-1c2fbd0e-29bd-4d8f-bb4c-3435596f511d.PNG
  alt: Terminal
  caption: Terminal (advanced users).

# TODO
featuredimage: https://user-images.githubusercontent.com/81830673/131410760-5b069670-9960-484b-adbc-1592cfc1f1ba.PNG

# TODO
# You only need the following if your plugin requires specific OctoPrint versions or
# specific operating systems to function - you can safely remove the whole
# "compatibility" block if this is not the case.

compatibility:

  # List of compatible versions
  #
  # A single version number will be interpretated as a minimum version requirement,
  # e.g. "1.3.1" will show the plugin as compatible to OctoPrint versions 1.3.1 and up.
  # More sophisticated version requirements can be modelled too by using PEP440
  # compatible version specifiers.
  #
  # You can also remove the whole "octoprint" block. Removing it will default to all
  # OctoPrint versions being supported.

  octoprint:
  - 1.2.0

  # List of compatible operating systems
  #
  # Valid values:
  #
  # - windows
  # - linux
  # - macos
  # - freebsd
  #
  # There are also two OS groups defined that get expanded on usage:
  #
  # - posix: linux, macos and freebsd
  # - nix: linux and freebsd
  #
  # You can also remove the whole "os" block. Removing it will default to all
  # operating systems being supported.

  os:
  - linux
  - windows
  - macos
  - freebsd

  # Compatible Python version
  #
  # Plugins should aim for compatibility for Python 2 and 3 for now, in which case the value should be ">=2.7,<4".
  #
  # Plugins that only wish to support Python 3 should set it to ">=3,<4".
  #
  # If your plugin only supports Python 2 (worst case, not recommended for newly developed plugins since Python 2
  # is EOL), leave at ">=2.7,<3" - be aware that your plugin will not be allowed to register on the
  # plugin repository if it only support Python 2.

  python: ">=2.7,<3"

---

This plugin interfaces with Safety Printer MCU (https://github.com/SinisterRj/SafetyPrinter) to improve your printer's safety.
You can find more information on Wiki (https://github.com/SinisterRj/SafetyPrinter/wiki).
P.S.: It also integrates with Octopod notifications, so is highly recommended its installation.
With this plugin you will be able to setup, supervise and trobleshoot your Safety Printer MCU. It provides: Sidebar sensor monitoring, Plugin and Sensor setup and Safety Printer MCU communications terminal (for advanced users).
