#!/usr/bin/env python3
"""
Sniffer do lado TCP do NPort — o mesmo que sniffer.py, mas por socket.

Roda no Computador B, com o NPort em TCP Server mode. Mostra em hexa os bytes
que o NPort tunela da porta serial, sem passar por decode nenhum.

Uso:
    python sniffer_tcp.py --host 192.168.127.254
        Escuta 10s sem transmitir. Com o Computador A parado, o esperado e
        ZERO byte. Se chegar enxurrada aqui, o barramento RS-485 esta gerando
        ruido sozinho e nao adianta mexer em baud rate.

    python sniffer_tcp.py --host 192.168.127.254 --enviar "PING-123"
        Transmite e mostra o que volta.
"""

import argparse
import socket
import sys
import time

from analise import diagnostico, formata_linha


def escuta(sock: socket.socket, segundos: float) -> bytes:
    """Le tudo que chegar durante a janela de tempo, imprimindo em hexa."""
    inicio = time.monotonic()
    dados = bytearray()
    pendente = bytearray()
    offset = 0

    while time.monotonic() - inicio < segundos:
        try:
            bloco = sock.recv(4096)
        except (socket.timeout, TimeoutError):
            continue
        except OSError as e:
            print(f"[conexao caiu: {e}]")
            break

        if not bloco:
            print("[conexao fechada pelo NPort]")
            break

        dados.extend(bloco)
        pendente.extend(bloco)
        while len(pendente) >= 16:
            print(formata_linha(offset, bytes(pendente[:16])))
            del pendente[:16]
            offset += 16

    if pendente:
        print(formata_linha(offset, bytes(pendente)))

    return bytes(dados)


def main() -> None:
    ap = argparse.ArgumentParser(description="Sniffer TCP do NPort em hexa")
    ap.add_argument("--host", default="192.168.127.254")
    ap.add_argument("--porta", type=int, default=4001)
    ap.add_argument("--segundos", type=float, default=10.0)
    ap.add_argument("--enviar", help="texto a transmitir antes de escutar")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect((args.host, args.porta))
    except OSError as e:
        print(f"Nao conectou em {args.host}:{args.porta} — {e}")
        print("Confira se o NPort esta em TCP Server mode (nao Real COM).")
        sys.exit(1)

    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.settimeout(0.5)

    with sock:
        enviados = 0
        if args.enviar:
            carga = f"{args.enviar}\n".encode("utf-8")
            sock.sendall(carga)
            enviados = len(carga)
            print(f"Enviados {enviados} bytes: {carga!r}")
        else:
            print("Modo escuta pura — nada sera transmitido por este lado.")
            print("Deixe o Computador A parado tambem: o esperado e ZERO byte.")

        print(f"Escutando {args.host}:{args.porta} "
              f"por {args.segundos:.0f}s...\n")
        dados = escuta(sock, args.segundos)

    if enviados and dados:
        print(f"\nrazao recebido/enviado: {len(dados) / enviados:.1f}x")

    diagnostico(dados, args.segundos, enviou=bool(args.enviar))


if __name__ == "__main__":
    main()
