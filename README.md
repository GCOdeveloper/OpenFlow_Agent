# OpenFlow_Agent

## Introduction
The OpenFlow_Agent is a development which allows to configure a PON network through a simple RPC connection to the OLT and presenting the entire network as a single SDN device, having as much ports as users ports on the real network. This code must be executed on a computer or a server which has connectivity with every OLT deployed. Although, another code is needed inside each OLT, which may be downloaded form another proyects, such as [opencord/openolt](https://github.com/opencord/openolt).

In order to add simplicity to the development, a menu-driven user interface has been created.

## Prerequisites
* git
* docker
* docker-hub
* openolt or another service with the right RPC server configured on the OLT.

## Installation
Firstly, clone the repository and enter on the created folder.

```shell
git clone https://github.com/GCOdeveloper/OpenFlow_Agent.git
cd OpenFlow_Agent
```

Then, edit the configuration file according your specific scenario (modify the IP address and port of the SDN controller and the OLT). If your deployment has more than one OLT, add them to the OLT array in JSON format. Here is a simply deployment example:

```shell
{
    "SDN-controller": {
        "ip_address": "10.0.60.2",
        "port": 6633
    },

    "olts": [
        {
            "ip_address": "10.10.50.116",
            "port": 9191,
            "voip_extension_start": 1111,
            "voip_extension_end": 9999
        }
    ]
}
```

Finally, execute the docker compose command.

```shell
docker-compose up -d --build
```

## OpenOLT
In order to achieve the correct communication with the OLT, it's a requeriment to install the openolt service on the OLT. It can be found on the public GitHub repository [opencord/openolt](https://github.com/opencord/openolt), where it's detailed the installation procedure.

## Contact
This development belongs to GCOdeveloper. GCO is the optical communications research group from the University of Valladolid, Spain. As mainteiner and manager of the project, the group main contact is Noemí Merayo, whose mail address is as follows:

[noemer@uva.es](mailto:noemer@uva.es)
