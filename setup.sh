#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p vendor/lib vendor/python
if [ ! -f logger/sof-logger.amd64 ]; then
  curl --fail --location --retry 3 https://sof1.megalag.org/sof-logger/download/sof-logger-2011-08-29.tar.gz -o vendor/original.tar.gz
  tar -xzf vendor/original.tar.gz -C vendor
  mv vendor/sof-logger-2011-08-29 logger
fi
chmod +x logger/sof-logger.amd64
for package in libncursesw5 libtinfo5; do
  curl --fail --location --retry 3 "https://archive.ubuntu.com/ubuntu/pool/main/n/ncurses/${package}_6.1-1ubuntu1.18.04.1_amd64.deb" -o "vendor/${package}.deb"
  dpkg-deb -x "vendor/${package}.deb" vendor/extracted
 done
cp -a vendor/extracted/lib/x86_64-linux-gnu/lib*.so* vendor/lib/
python3 -m pip install --upgrade --target vendor/python 'aiohttp==3.13.5'
rm -f vendor/*.deb vendor/original.tar.gz
printf 'Installation complete. Configure Startup variables, then start the server.\n'
