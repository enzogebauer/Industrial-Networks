# Comunicação entre dois dispositivos através de gateway conversor de meio físico

Dois computadores trocam mensagens atravessando um gateway que converte o meio
físico: de **RS-485** (serial, elétrico, half-duplex) para **Ethernet** (TCP/IP).

```
Computador A          USB-i485          NPort 5150         Computador B
  (serial)   --USB-->  (conversor) --RS-485--> (gateway) --Ethernet-->  (socket TCP)
chat_serial.py                       2 fios                        chat_tcp_nport.py
```

O ponto da montagem: **nenhum dos dois lados conhece o meio do outro.** O A
escreve bytes numa porta serial e não sabe que existe rede. O B abre um socket
TCP e não sabe que existe RS-485. O NPort 5150 traduz no meio, tunelando os
bytes crus de um meio para o outro sem interpretá-los.

```bash
pip install -r requirements.txt
```

---

## Meio físico escolhido: RS-485 2 fios

| | |
|---|---|
| **Topologia** | Barramento multiponto, até 32 dispositivos no mesmo par |
| **Sinalização** | Diferencial — o bit é a diferença de tensão entre os dois fios |
| **Duplex** | Half-duplex: o par é compartilhado, um transmite por vez |
| **Formato** | 9600 8N1 (1 start + 8 dados + 1 stop) |

A sinalização diferencial é o motivo de o RS-485 aguentar centenas de metros
onde o RS-232 não passa de alguns: o ruído entra igual nos dois fios e a
subtração o cancela. O preço é o half-duplex — como os dois lados dividem o
mesmo par, o transceptor precisa inverter o sentido entre transmitir e receber,
e nesse intervalo ninguém escuta.

---

## Scripts

| Arquivo | Onde roda | O que faz |
|---|---|---|
| `chat_serial.py` | A | Chat bidirecional pela porta serial, atravessando o RS-485 |
| `chat_tcp_nport.py` | B | Chat pelo outro lado do gateway, via socket TCP puro |
| `diagnostico.py` | A e B | Lista portas, testa loopback físico, testa alcance TCP do NPort |
| `sniffer.py` | A | Mostra os bytes crus em hexa e separa problema elétrico de baud rate |
| `sniffer_tcp.py` | B | O mesmo, pelo lado TCP do gateway |
| `portas.py` | — | Acha a porta do conversor pelo VID do chip FTDI |
| `analise.py` | — | Interpretação dos bytes recebidos, usada pelos dois sniffers |

O `step-by-step.md` traz a montagem física e a configuração do NPort, na ordem
em que precisam ser feitas.

---

## Ordem de execução

### 1. Antes de qualquer código

```bash
# Computador A
python diagnostico.py
```

Lista as portas seriais. O USB-i485 usa chip FTDI (VID `0403`) — o script
sinaliza quando encontra. Se nada aparecer, o problema é driver ou cabo.

Do lado do gateway:

```bash
# Computador B
python diagnostico.py --tcp 192.168.127.254:4001
```

### 2. A comunicação

```bash
# Computador A
python chat_serial.py --nome A

# Computador B
python chat_tcp_nport.py --host 192.168.127.254 --nome B
```

Digite dos dois lados. A mensagem digitada no A sai como bytes seriais, cruza o
RS-485, entra no NPort, sai como TCP e aparece no B — e vice-versa.

O `chat_serial.py` acha a porta do conversor sozinho pelo VID do FTDI; passe
`--porta` só se houver mais de um dispositivo FTDI na máquina.

### 3. Se aparecer lixo em vez de texto

Pare o chat e use o sniffer. O chat decodifica tudo como UTF-8, e isso apaga a
informação que resolve o caso — `0x00`, `0xFF` e `0x93` viram o mesmo caractere
na tela, mas apontam para causas diferentes.

```bash
# Computador A — escuta pura, ninguém digitando dos dois lados
python sniffer.py --segundos 120

# Computador B
python sniffer_tcp.py --host 192.168.127.254 --segundos 120
```

Byte chegando com ninguém transmitindo é problema elétrico, e nenhuma mudança
de baud rate resolve. Se o lixo só aparece quando alguém transmite, aí sim é
divergência de configuração serial entre as pontas.

Para descobrir a taxa de quem está transmitindo:

```bash
python sniffer.py --varrer --segundos 30
```

---

## Testando sem hardware

Dá para validar a lógica dos dois lados antes de ter os equipamentos, usando o
`socat` para criar um par de portas seriais virtuais ligadas entre si:

```bash
socat pty,raw,echo=0,link=/tmp/ttyA pty,raw,echo=0,link=/tmp/ttyB &

python chat_serial.py --porta /tmp/ttyA --nome A &
python chat_serial.py --porta /tmp/ttyB --nome B
```

No Windows o equivalente é o com0com. Vale a pena: separa erro de código de
erro de fiação, que é onde se perde mais tempo nesse tipo de montagem. As
portas virtuais não têm VID, então aqui o `--porta` é obrigatório.

---

## Duas armadilhas

**O gateway não interpreta nada.** O NPort em TCP Server mode faz tunelamento
cru: os bytes que entram pela serial saem pelo socket sem tradução de conteúdo.
Ele converte meio físico, não protocolo. Isso é o que permite o chat funcionar
com socket puro dos dois lados — e é também o que faz qualquer ruído elétrico
no barramento chegar como dado no outro lado.

**Half-duplex tem tempo morto.** Em RS-485 de 2 fios o barramento é
compartilhado: enquanto um lado transmite, ninguém mais pode. O transceptor
precisa de alguns microssegundos para virar de transmissão para recepção. O
USB-i485 faz essa comutação automaticamente por hardware, mas o Latency Timer
do driver FTDI (4 ms, não 16) ainda influencia a resposta percebida.
