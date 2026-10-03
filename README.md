# SoF Logger Web v1.0.0

Runs the **original Linux amd64 SoF logger (2011-08-29)** in a pseudo-terminal and bridges its input and output to a browser. The logger's player list, colour rendering, original selection controls, IP/name logging, kick/reconnect rejection, bans, access levels and RCON mode are supplied by the original executable. This is a browser terminal, not a redesigned dashboard. Its behaviour remains that of the original version, including its limitations and polling delays.

## Pterodactyl installation

Requires a Linux **amd64** Wings node and panel administrator access to import an egg. No Discord bot is needed. The logger can monitor a SoF server on a different machine.

1. Import `egg-sof-logger-web.json` in Admin → Nests → Import Egg.
2. Create a **separate** server using the SoF Logger Web egg, Python 3.12 image, and one unused TCP allocation (for example 8080). Suggested starting resources: 256 MB RAM, 512 MB disk, 50% CPU; adjust based on usage. The first install deliberately stops until the files have been uploaded.
3. Upload this ZIP through Files and unarchive it in the server root. `server.py`, `setup.sh`, `public/`, and `egg-sof-logger-web.json` must be directly in `/home/container`, not inside an extra folder.
4. Click Reinstall. The installer downloads the logger from its author, its ncurses compatibility libraries from Ubuntu, and the Python web dependencies. It preserves an existing `logger/` directory and player/access history. **Back up before reinstalling.**
5. Set Startup variables:
   - `SOF_SERVER_IP`: your game server's reachable IP or hostname.
   - `SOF_SERVER_PORT`: game UDP port, commonly 28910.
   - `SOF_RCON_PASSWORD`: matching game server RCON password.
   - `WEB_USER`: default `admin`.
   - `WEB_PASSWORD`: a separate web password, at least 12 characters.
   - `PUBLIC_URL`: leave empty for direct HTTP access; set to `https://logger.yourdomain.com` for HTTPS through a reverse proxy.
6. Start. Open `http://NODE-IP:ALLOCATED-PORT` and sign in. The service binds to the primary allocation via `SERVER_PORT`. This address is the Wings node address, not necessarily the panel's address.

The Python yolk must have the x86-64 glibc loader and Python 3.12. If your hosting provider supplies a different image or cannot pull that yolk, the included Dockerfile builds an alternative image: `docker build -t YOUR-REGISTRY/sof-logger-web:1 .`, then push it and select it in the egg. The Dockerfile builds the runtime only; the panel installer still sets up application files.

## Domain / HTTPS

Point a domain's DNS at the reverse proxy, proxy to the allocated logger TCP port, and enable WebSocket support. Set PUBLIC_URL to the exact public origin (scheme + hostname + optional port, no path). The service is intended at the root of a dedicated subdomain. A proxy must preserve `Host` and WebSocket upgrade headers. Example Nginx location inside your existing TLS-enabled virtual host:

```nginx
location / {
    proxy_pass http://WINGS_NODE_IP:LOGGER_WEB_PORT;
    proxy_http_version 1.1;
    proxy_set_header Host $http_host;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 3600s;
}
```

Use HTTPS for Internet access. Direct HTTP is useful for initial local setup but does not encrypt the login or control traffic. The Pterodactyl panel does not itself publish or proxy this web page. The allocation/firewall must allow inbound TCP; the container must reach the game server by UDP. Ephemeral client UDP ports are selected automatically; no separate inbound UDP allocation is needed for ordinary polling replies.

## Controls and stored files

- Click the terminal before typing. Use the original keyboard selection controls.
- F1 or `~` switches RCON console mode. Enter commands **without** a leading `rcon`.
- K kicks; B bans; + and - adjust access; Q exits the logger. The supplied buttons send those same keys to the current mode. In console mode they are characters, not independent actions.
- The fixed terminal is 140 columns × 40 rows. Narrow screens scroll horizontally.
- All browsers share one logger and selection. Coordinate with other administrators. Closing a browser leaves the logger running.
- If Q quits the logger, restart the Pterodactyl server to run it again.
- Edit optional original settings in `logger/sof-logger.cfg` via SFTP while stopped. Connection settings are replaced by Startup variables. The file is denied by panel file access because it contains the RCON password.
- Persistent logs, name/IP history, and access files remain in `logger/data/`. Back up this folder and the configuration. Changes by the original logger follow its own save behaviour.
- Web login sessions expire after 8 hours and are cleared on process restart. Logout closes that session's live sockets. There is one admin credential and no read-only user role.

## Attribution and limitations

Original program and documentation: https://sof1.megalag.org/sof-logger/
The original executable is downloaded directly during installation, not redistributed in this package. Original source code is not included in the published archive. Terminal assets: xterm.js 5.5.0, MIT license in `public/XTERM-LICENSE`. Ubuntu ncurses package copyright files are retained under `vendor/extracted/usr/share/doc/` after setup.

The web bridge and login were tested locally with a simulated UDP SoF endpoint. Real player selection, kick, ban and access enforcement still require verification against your live SoF/SoFplus server. The target Pterodactyl node and reverse proxy have not been accessed or configured. The original binary is from 2011; this wrapper does not fix bugs inside it. Terminal glyphs can differ slightly from the old native console.

## Containers on the same Wings node

The game server public IP may not accept connections originating from another container on the same node. Test the game container internal IP and game UDP port. This deployment was confirmed to receive a SoF status response through the game container internal address, while its public address timed out. Container addresses vary and may change after recreation; do not copy another installation's address.

## Troubleshooting

- `No module named aiohttp`: complete Reinstall after uploading files. The installer uses Python 3.12, matching the runtime. If necessary, use the startup command below to replace old dependency files.
- Missing `logger/sof-logger.cfg`: setup did not finish. Ensure `setup.sh` is at the server root, then Reinstall and check the installation log.
- Origin mismatch: PUBLIC_URL must equal the browser origin, including scheme and port. Open `/`, rather than navigating to `/login` directly.
- A green Connected label indicates the browser terminal connection, not game server connectivity. Test UDP and RCON separately if the game field remains blank.

Dependency repair startup command:

```bash
python3 -m pip install --upgrade --target /home/container/vendor/python -r /home/container/requirements.txt && PYTHONPATH=/home/container/vendor/python python3 /home/container/server.py
```

## GitHub release

Upload the files from this archive to the repository root (extract the ZIP first). Commit, create tag `v1.0.0`, then create a GitHub Release titled `SoF Logger Web v1.0.0`. Attach this source ZIP if desired. The repo needs no credentials or original executable. The original logger and compatibility dependencies are downloaded by setup.

The MIT license covers this project's web wrapper and setup files only. Original logger rights belong to its author; ncurses and xterm.js retain their respective licenses.
