#!/usr/bin/env python3
"""
Descoberta automatica da porta do USB-i485.

O nome da porta nao e estavel. No macOS ele codifica em qual conector USB o
cabo esta ligado — cu.usbserial-120, -130, -1130 — entao muda sozinho quando
se troca de entrada ou de hub. No Linux vira ttyUSB0, ttyUSB1... conforme a
ordem de conexao. Fixar o nome no comando funciona hoje e quebra na proxima
replugada, com uma mensagem de erro que parece problema de driver.

Como o USB-i485 usa chip FTDI (VID 0x0403), da para achar a porta pelo VID em
vez de decorar o nome.
"""

import serial.tools.list_ports

VID_FTDI = 0x0403


def detectar(preferida: str = "auto") -> str:
    """Resolve qual porta usar.

    Um nome explicito sempre vence — necessario quando ha mais de um
    dispositivo FTDI na maquina, ou para portas virtuais (socat, com0com),
    que nao tem VID nenhum.
    """
    if preferida and preferida != "auto":
        return preferida

    candidatas = [p for p in serial.tools.list_ports.comports()
                  if p.vid == VID_FTDI]

    if not candidatas:
        raise SystemExit(
            "Nenhuma porta FTDI encontrada.\n"
            "  - USB-i485 desconectado, ou\n"
            "  - driver VCP da FTDI nao instalado\n"
            "Rode 'python diagnostico.py' para ver o que existe."
        )

    if len(candidatas) > 1:
        nomes = ", ".join(p.device for p in candidatas)
        raise SystemExit(
            f"Mais de uma porta FTDI conectada: {nomes}\n"
            "Passe --porta com a que voce quer."
        )

    return candidatas[0].device
