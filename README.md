# Código — link serial entre dois computadores

Scripts Python para o Computador A (USB-i485) e o Computador B (NPort 5150).

```bash
pip install -r requirements.txt
```

Versões travadas de propósito. O `pymodbus` quebrou compatibilidade entre a
série 2.x e a 3.x (o import `pymodbus.client.sync` sumiu, `unit=` virou
`slave=`), então código de tutorial antigo não roda em versão nova.

---

## As duas camadas

O ponto que costuma confundir: **existem dois protocolos empilhados**, e eles
resolvem problemas diferentes.

| Camada | O que é | Biblioteca |
|---|---|---|
| **Transporte** | Como os bytes chegam de um lado ao outro: RS-485 (elétrico) e TCP/IP (rede) | `pyserial`, `socket` |
| **Aplicação** | O que os bytes significam: quem pergunta, quem responde, onde estão os dados | `pymodbus` |

Você pode usar só a camada de transporte (o chat cru, bytes soltos), ou empilhar
Modbus por cima para ter algo estruturado. Os dois conjuntos de scripts abaixo
fazem exatamente isso.

---

## Scripts

| Arquivo | Onde roda | O que faz |
|---|---|---|
| `diagnostico.py` | qualquer | Lista portas, testa loopback físico, testa alcance TCP do NPort |
| `sniffer.py` | A e B | Mostra os bytes crus em hexa e diz se o problema é elétrico ou de baud |
| `sniffer_tcp.py` | B | O mesmo, pelo lado TCP do NPort |
| `chat_serial.py` | A e B | Chat bidirecional de texto cru. Mesmo script nos dois lados |
| `chat_tcp_nport.py` | B | Chat pelo lado B via socket puro, sem driver Real COM |
| `modbus_slave.py` | A | Escravo Modbus RTU simulando um sensor |
| `modbus_master.py` | B | Mestre Modbus consultando o escravo (serial ou TCP) |

---

## Ordem de execução

### Etapa 1 — Antes de qualquer código

```bash
python diagnostico.py
```

Lista as portas seriais. O USB-i485 usa chip FTDI (VID `0403`) — o script
sinaliza quando encontra. Se nada aparecer, o problema é driver ou cabo, não
código.

Para validar a fiação sem depender do NPort, ponteie Rx+ com Tx+ e Rx- com Tx-
no bloco de terminais e rode:

```bash
python diagnostico.py --porta /dev/ttyUSB0
```

O que for escrito volta idêntico. Se voltar embaralhado, é baud rate; se não
voltar nada, é a ponte ou o MOD (pino 4) indevidamente conectado.

Com o NPort na rede:

```bash
python diagnostico.py --tcp 192.168.127.254:4001
```

### Etapa 2 — Chat cru (valida o caminho completo)

Faça isso antes de partir para Modbus. Se o texto não passa, Modbus também não vai.

Com o NPort em **TCP Server mode**, que é o caminho do `step-by-step.md` — sem
driver proprietário em lugar nenhum:

```bash
# Computador A
python chat_serial.py --porta /dev/ttyUSB0 --nome A

# Computador B
python chat_tcp_nport.py --host 192.168.127.254 --nome B
```

Ou, com o NPort em **Real COM mode** e o driver da MOXA instalado no B, que
mapeia o gateway como uma COM virtual e deixa o mesmo script rodar nos dois lados:

```bash
# Computador B
python chat_serial.py --porta COM5 --nome B
```

Os dois modos são exclusivos: exigem configurações diferentes em Operating
Settings. Escolha um e siga inteiro.

Se aparecer lixo na tela em vez de texto, pare o chat e use o sniffer — ele
mostra o byte cru e separa problema elétrico de baud rate divergente:

```bash
python sniffer.py --porta /dev/ttyUSB0 --segundos 10       # A
python sniffer_tcp.py --host 192.168.127.254 --segundos 10  # B
```

### Etapa 3 — Modbus RTU

```bash
# Computador A
python modbus_slave.py --porta /dev/ttyUSB0 --slave-id 1

# Computador B — via TCP direto (NPort em TCP Server mode)
python modbus_master.py tcp --host 192.168.127.254 --slave-id 1

# Computador B — via COM virtual (NPort em Real COM mode)
python modbus_master.py serial --porta COM5 --slave-id 1

# Escrevendo um setpoint no escravo
python modbus_master.py tcp --host 192.168.127.254 --setpoint 42
```

Saída esperada no mestre:

```
Conectado (serial). Consultando escravo id=1.

  ciclo=    5   temperatura=25.5 C
  ciclo=    6   temperatura=25.6 C
  ciclo=    7   temperatura=25.7 C
```

E no escravo, quando o mestre escreve:

```
2026-08-17 22:17:37  setpoint recebido do mestre: 42
```

---

## Testando sem hardware

Dá para validar toda a lógica antes de ter os equipamentos em mãos, usando o
`socat` para criar um par de portas seriais virtuais ligadas entre si:

```bash
socat pty,raw,echo=0,link=/tmp/ttyA pty,raw,echo=0,link=/tmp/ttyB &

python modbus_slave.py --porta /tmp/ttyA --slave-id 1 &
python modbus_master.py serial --porta /tmp/ttyB --slave-id 1
```

No Windows o equivalente é o com0com. Vale a pena: separa erro de código de
erro de fiação, que é onde se perde mais tempo nesse tipo de montagem.

---

## Duas armadilhas

**Modbus RTU sobre TCP não é Modbus TCP.** O NPort em TCP Server mode faz
tunelamento cru — os bytes que chegam pelo socket ainda são frames RTU com CRC.
Modbus TCP é outro formato: tem cabeçalho MBAP e dispensa CRC, porque o TCP já
garante integridade. Por isso `modbus_master.py` passa `framer=ModbusRtuFramer`
no `ModbusTcpClient`. Sem isso, a conexão TCP abre normalmente e nenhuma
resposta é decodificada — parece problema de fiação, mas é de framing.

**Half-duplex tem tempo morto.** Em RS-485 de 2 fios o barramento é
compartilhado: enquanto um lado transmite, ninguém mais pode. O transceptor
precisa de alguns microssegundos para virar de transmissão para recepção. O
USB-i485 faz essa comutação automaticamente por hardware, mas se o timeout do
mestre for curto demais ele desiste antes de o escravo conseguir responder. Se
aparecerem timeouts intermitentes, aumente o `timeout` do cliente antes de
suspeitar do cabo — e confira o Latency Timer do driver FTDI (4 ms, não 16).
