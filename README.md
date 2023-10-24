# OpenFlow_Agent

## Introduction
The OpenFlow_Agent is a development which allows to configure a PON network through a simple RPC connection to the OLT and presenting the entire network as a single SDN device, having as much ports as users ports on the real network. This code must be executed on a computer or a server which has connectivity with every OLT deployed. Although, another code is needed inside each OLT, which may be downloaded form another projects, such as [opencord/openolt](https://github.com/opencord/openolt).

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
To achieve a correct communication with the OLT, it is necessary to install the openolt service on the OLT. It can be found in the public GitHub repository [opencord/openolt](https://github.com/opencord/openolt), where the installation procedure is detailed.

## Publications

D. de Pintos, N. Merayo, C. Sangrador, J. C. Aguado, I. de Miguel and R. J. Duran Barroso, "Software defined networking agent demonstration to enable configuration and management of XGS-PON architectures," in Journal of Optical Communications and Networking, vol. 15, no. 9, pp. 620-637, September 2023, ([doi: 10.1364/JOCN.494694](https://doi.org/10.1364/JOCN.494694)).

** Funding Information** .  This research is supported by Consejería de Educación de la Junta de Castilla y León and the European Regional Development Fund (Grant VA231P20) and by Ministerio de Ciencia e Innovación / Agencia Estatal de Investigación (Grant PID2020-112675RB-C42 funded by MCIN/AEI/10.13039/501100011033).

** Acknowledgment** . We are grateful to Telnet R.I. for the supply of XGS-PON equipment (OLT, ONUs).
**This is bold text**

## Contact
This development belongs to GCOdeveloper. GCO is the optical communications research group at the University of Valladolid, Spain. As project leader and manager, the main contact of the group is Noemí Merayo, whose e-mail address is as follows:

[noemer@uva.es](mailto:noemer@uva.es)
