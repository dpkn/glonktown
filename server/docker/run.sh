#!/bin/sh
# Open Toontown, everything in one container: Astron, UberDOG, one district, the web bridge, the sign-in service, nginx and nightly backups.
if [ ! -d /ot/src/resources/phase_3 ]; then
  echo "The game's resources are missing: mount your resources folder (with phase_3, phase_4 and the rest) at /ot/src/resources" >&2
  exit 1
fi
mkdir -p /ot/data/phone_logs /ot/data/backups /ot/data/logs /ot/src/astron/databases/astrondb /ot/src/astron/logs
[ -f /ot/data/users.json ] || echo '{"open_registration": true, "users": {}}' > /ot/data/users.json
# the key the sign-in service signs play tokens with and the login manager checks them with
[ -s /ot/data/login_secret ] || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n' > /ot/data/login_secret
chmod 600 /ot/data/login_secret
chmod 666 /ot/data/users.json
L=/ot/data/logs
# the services write their own log files (so they survive in the data folder); show them in `docker logs` / the Zima's Logs tab too
for f in auth bridge astron ud ai1 client; do touch $L/$f.log; done
echo "Open Toontown: starting. The district opens in about a minute and a half."
tail -n 0 -F $L/auth.log $L/bridge.log $L/astron.log $L/ud.log $L/ai1.log $L/client.log 2>/dev/null &
nginx
python -u /ot/auth_service.py > $L/auth.log 2>&1 &
python -u /ot/wsbridge.py > $L/bridge.log 2>&1 &
cd /ot/src/astron/linux && chmod +x astrond && ./astrond --loglevel info ../config/astrond-linux.yml > $L/astron.log 2>&1 &
sleep 6
cd /ot/src
COMMON="--max-channels 999999 --stateserver 4002 --messagedirector-ip 127.0.0.1:7199 --eventlogger-ip 127.0.0.1:7197"
python -u -m toontown.uberdog.UDStart --base-channel 1000000 $COMMON etc/Configrc.prc etc/live.prc > $L/ud.log 2>&1 &
UD=$!
sleep 25
python -u -m toontown.ai.AIStart --base-channel 401000000 $COMMON --district-name "Toon Valley" etc/Configrc.prc etc/live.prc > $L/ai1.log 2>&1 &
A1=$!
# nightly backup of the toons, users and planned parties, keeping 14 days
( while true; do sleep 86400; tar czf /ot/data/backups/auto-$(date +%Y%m%d-%H%M).tgz -C /ot/src/astron databases -C /ot/data users.json parties.json 2>/dev/null; ls -1t /ot/data/backups/auto-*.tgz | tail -n +15 | xargs -r rm -f; done ) &
# if the UberDOG or a district dies, exit so Docker restarts everything
while kill -0 $UD 2>/dev/null && kill -0 $A1 2>/dev/null; do sleep 20; done
echo "a game process died; exiting so the container restarts" >&2
exit 1
