Dynamic domain name server
==========================

This directory contains all the needed files to set up a dynamic DNS
server that can be refreshed by the other containers.

First edit your `build.conf` file to build the DNS container:

    ["dockerops-base","demo","dns"]

Then build the images:

    dockerops build:all

To use the service simply edit the `run.conf` file and change the
following lines:

    [

     {
      "container": "dockerops-base",
      "instance": "one",
      "sleep": 0,
      "links": []
      },

     {
      "container": "demo",
      "instance": "one",
      "sleep": 0,
      "links": [
                 {
                   "name": "BASE",
                   "container": "dockerops-base",
                   "instance": null
                  }
                ]
      }

     ]

into these lines:

    [

     {
      "container": "dns",
      "instance": "master",
      "sleep": 0,
      "links": []
      },

     {
      "container": "demo",
      "instance": "one",
      "sleep": 0,
      "links": [
                 {
                   "name": "DNS",
                   "container": "dns",
                   "instance": null
                  }
                ]
      }

     ]

Start the containers and you should be able to contact the DNS container
and ask it your local zone members (e.g. via `nslookup`).

