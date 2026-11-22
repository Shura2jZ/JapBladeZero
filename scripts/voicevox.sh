#!/usr/bin/env bash
# Demarre, arrete ou interroge les moteurs VOICEVOX.
#
#   bash scripts/voicevox.sh start [N]   N moteurs (4 par defaut)
#   bash scripts/voicevox.sh stop
#   bash scripts/voicevox.sh status
#
# Chaque moteur charge son modele (plusieurs Go de RAM) etSat numerosement le
# CPU : un moteur de trop se sent. 4 moteurs suffisent pour le pipeline, qui
# travaille avec VOICEVOX_PORTS et VOICEVOX_WORKERS (voir scripts/tts.sh).
set -uo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE"

RUN="${VOICEVOX_RUN:-E:/PBZ_Build/voicevox/windows-cpu/run.exe}"
COUNT="${2:-4}"
FIRST_PORT=50021
PORTS=()
for i in $(seq 0 $((COUNT - 1))); do
    PORTS+=($((FIRST_PORT + i)))
done

case "${1:-status}" in
start)
    if [ ! -f "$RUN" ]; then
        echo "moteur introuvable : $RUN" >&2
        exit 1
    fi
    for p in "${PORTS[@]}"; do
        if curl -s -m 3 "http://127.0.0.1:$p/version" > /dev/null 2>&1; then
            echo "moteur $p deja demarre"
            continue
        fi
        nohup "$RUN" --host 127.0.0.1 --port "$p" --no-use_gpu \
            --output_log_utf8 --init_processes 1 \
            > "logs/vv_$p.log" 2>&1 &
        echo "moteur $p demarre"
    done
    echo "attente du chargement des modeles..."
    for p in "${PORTS[@]}"; do
        for _ in $(seq 1 40); do
            if curl -s -m 3 "http://127.0.0.1:$p/version" > /dev/null 2>&1; then
                break
            fi
            sleep 2
        done
    done
    echo "moteurs prets : ${PORTS[*]}"
    ;;
stop)
    taskkill //F //IM run.exe > /dev/null 2>&1
    echo "moteurs arretes"
    ;;
status)
    for p in "${PORTS[@]}"; do
        printf "%s: %s\n" "$p" "$(curl -s -m 3 "http://127.0.0.1:$p/version" || echo 'absent')"
    done
    ;;
*)
    echo "usage : bash scripts/voicevox.sh {start|stop|status} [nombre de moteurs]" >&2
    exit 1
    ;;
esac
