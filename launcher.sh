#! /bin/bash

# sleep for 5 seconds; this is especially imporant during reboot
# otherwise, the script would crash due to a 'no connectivity' error
sleep 5

__dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd ${__dir}
python3 pompfbot.py & 
