#!/usr/bin/env python3
"""
Computador A — escravo Modbus RTU sobre RS-485.

Simula um dispositivo de campo (um CLP, um transmissor de temperatura) que
fica escutando o barramento e responde quando o mestre pergunta por ele.

Uso:
    python modbus_slave.py --porta /dev/ttyUSB0 --slave-id 1

pymodbus 3.6.x. Se voce usar outra versao major, a API muda de nome.
"""

import argparse
import logging
import threading
import time

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)
from pymodbus.framer.rtu_framer import ModbusRtuFramer
from pymodbus.server import StartSerialServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger(__name__)


def montar_contexto() -> tuple[ModbusServerContext, ModbusSlaveContext]:
    """
    Modbus tem quatro tabelas de dados. As duas mais usadas:
      - holding registers (hr): 16 bits, leitura E escrita  -> setpoints
      - input registers   (ir): 16 bits, so leitura         -> medicoes
    """
    store = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [False] * 16),   # discrete inputs
        co=ModbusSequentialDataBlock(0, [False] * 16),   # coils
        hr=ModbusSequentialDataBlock(0, [0] * 16),       # holding registers
        ir=ModbusSequentialDataBlock(0, [0] * 16),       # input registers
        zero_mode=True,  # endereco 0 no protocolo = indice 0 aqui
    )
    return ModbusServerContext(slaves=store, single=True), store


def simular_sensor(store: ModbusSlaveContext, parar: threading.Event) -> None:
    """
    Atualiza os input registers como se fossem leituras reais.
    Registrador 0: contador de ciclos
    Registrador 1: 'temperatura' em decimos de grau (250 = 25.0 C)
    """
    ciclo = 0
    while not parar.is_set():
        ciclo = (ciclo + 1) % 65536
        temperatura = 250 + (ciclo % 40)

        # 4 = input registers na convencao do pymodbus
        store.setValues(4, 0, [ciclo, temperatura])

        # Le o que o mestre eventualmente escreveu no holding register 0
        setpoint = store.getValues(3, 0, count=1)[0]  # 3 = holding registers
        if setpoint:
            log.info("setpoint recebido do mestre: %d", setpoint)

        time.sleep(1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", required=True)
    ap.add_argument("--baudrate", type=int, default=9600)
    ap.add_argument("--slave-id", type=int, default=1)
    args = ap.parse_args()

    context, store = montar_contexto()

    parar = threading.Event()
    threading.Thread(target=simular_sensor, args=(store, parar), daemon=True).start()

    log.info("Escravo Modbus RTU id=%d em %s @ %d bps",
             args.slave_id, args.porta, args.baudrate)
    log.info("Aguardando o mestre. Ctrl+C para sair.")

    try:
        StartSerialServer(
            context=context,
            framer=ModbusRtuFramer,
            port=args.porta,
            baudrate=args.baudrate,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=1,
        )
    except KeyboardInterrupt:
        log.info("Encerrando.")
    finally:
        parar.set()


if __name__ == "__main__":
    main()
