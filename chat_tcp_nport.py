#!/usr/bin/env python3
"""
Lado B SEM o driver Real COM da MOXA.

Se voce configurar o NPort em "TCP Server mode" no console web, ele passa a
escutar em uma porta TCP e faz tunelamento cru dos bytes seriais. Ai da para
falar com ele com socket puro — nenhum driver proprietario, roda igual em
Linux, macOS e Windows.

Portas padrao do NPort:
    4001  dados da porta serial 1
    966   comando (controle de parametros seriais via API)

Uso:
    python chat_tcp_nport.py --host 192.168.127.254
"""

import argparse
import socket
import sys
import threading


def leitor(sock: socket.socket, parar: threading.Event) -> None:
    buffer = bytearray()
    while not parar.is_set():
        try:
            dados = sock.recv(1024)
        except (socket.timeout, TimeoutError):
            continue
        except OSError:
            break

        if not dados:
            print("\n[conexao fechada pelo NPort]")
            parar.set()
            return

        buffer.extend(dados)
        while b"\n" in buffer:
            linha, _, resto = buffer.partition(b"\n")
            buffer = bytearray(resto)
            texto = linha.decode("utf-8", errors="replace").rstrip("\r")
            print(f"\r<< {texto}\n>> ", end="", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="192.168.127.254")
    ap.add_argument("--porta", type=int, default=4001)
    ap.add_argument("--nome", default="B")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect((args.host, args.porta))
    except OSError as e:
        print(f"Nao conectou em {args.host}:{args.porta} — {e}")
        print("Confira se o NPort esta em TCP Server mode (nao Real COM).")
        sys.exit(1)

    # TCP_NODELAY desliga o algoritmo de Nagle. Sem isso o SO segura pacotes
    # pequenos esperando juntar mais dados — o que atrasa mensagens curtas.
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.settimeout(0.5)

    print(f"Conectado em {args.host}:{args.porta}")
    print("Digite e pressione Enter. Ctrl+C para sair.\n")

    parar = threading.Event()
    threading.Thread(target=leitor, args=(sock, parar), daemon=True).start()

    try:
        while True:
            texto = input(">> ")
            if not texto:
                continue
            sock.sendall(f"[{args.nome}] {texto}\n".encode("utf-8"))
    except (KeyboardInterrupt, EOFError):
        print("\nEncerrando.")
    finally:
        parar.set()
        sock.close()


if __name__ == "__main__":
    main()
