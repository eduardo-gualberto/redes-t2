import asyncio
from tcputils import *
import os
import random


class Servidor:
    def __init__(self, rede, porta):
        self.rede = rede
        self.porta = porta
        self.conexoes = {}
        self.callback = None
        self.rede.registrar_recebedor(self._rdt_rcv)

    def registrar_monitor_de_conexoes_aceitas(self, callback):
        """
        Usado pela camada de aplicação para registrar uma função para ser chamada
        sempre que uma nova conexão for aceita
        """
        self.callback = callback

    def kill_conexao(self, conexao):
        src_addr, src_port, dst_addr, dst_port = conexao.id_conexao
        new_segment = make_header(
            dst_port, src_port, 1, conexao.seq_no + 1, FLAGS_ACK)
        FIN_dados = [new_segment, dst_addr]
        self.rede.enviar(FIN_dados[0], FIN_dados[1])
        self.conexoes.pop(conexao.id_conexao)
        pass

    def _rdt_rcv(self, src_addr, dst_addr, segment):
        src_port, dst_port, seq_no, ack_no, \
            flags, window_size, checksum, urg_ptr = read_header(segment)

        if dst_port != self.porta:
            # Ignora segmentos que não são destinados à porta do nosso servidor
            return
        if not self.rede.ignore_checksum and calc_checksum(segment, src_addr, dst_addr) != 0:
            print('descartando segmento com checksum incorreto')
            return

        payload = segment[4*(flags >> 12):]
        id_conexao = (src_addr, src_port, dst_addr, dst_port)

        if (flags & FLAGS_SYN) == FLAGS_SYN:
            # A flag SYN estar setada significa que é um cliente tentando estabelecer uma conexão nova
            # TODO: talvez você precise passar mais coisas para o construtor de conexão
            conexao = self.conexoes[id_conexao] = Conexao(self, id_conexao)
            # Não Tenho certeza disso aqui em baixo
            conexao.expected_seq_no = seq_no + 1
            new_seq_no = random.randint(1, 1000)
            # TODO: você precisa fazer o handshake aceitando a conexão. Escolha se você acha melhor
            # fazer aqui mesmo ou dentro da classe Conexao.
            new_segment = fix_checksum(make_header(
                dst_port, src_port, new_seq_no, seq_no + 1, FLAGS_SYN+FLAGS_ACK), dst_addr, src_addr)
            print("do meu, new_seq_no = ", new_seq_no)
            print("seq num cliente = ", seq_no)
            dados = [new_segment, src_addr]
            conexao.seq_no = new_seq_no
            self.rede.enviar(dados[0],dados[1])
            if self.callback:
                self.callback(conexao)
        elif id_conexao in self.conexoes:
            # Passa para a conexão adequada se ela já estiver estabelecida
            self.conexoes[id_conexao]._rdt_rcv(seq_no, ack_no, flags, payload)

        else:
            print('%s:%d -> %s:%d (pacote associado a conexão desconhecida)' %
                  (src_addr, src_port, dst_addr, dst_port))

        if (flags & FLAGS_FIN) == FLAGS_FIN:
            curr_conexao = self.conexoes[id_conexao]
            # ENVIAR ACK
            new_segment = make_header(
                dst_port, src_port, seq_no, seq_no + 1, FLAGS_ACK)
            ACK_dados = [new_segment, src_addr]
            curr_conexao.enviar(ACK_dados)
            curr_conexao.seq_no += 1

            # EXECUTAR CALLBACK DA CONEXAO COM DADOS = b''
            curr_conexao.callback(curr_conexao, b'')

            # O ENVIO DO 'FIN' É TRATADO EM conexao.fechar()


class Conexao:
    def __init__(self, servidor, id_conexao):
        self.servidor = servidor
        self.id_conexao = id_conexao
        self.callback = None
        self.seq_no = None
        self.expected_seq_no = None
        # um timer pode ser criado assim; esta linha é só um exemplo e pode ser removida
        self.timer = asyncio.get_event_loop().call_later(1, self._exemplo_timer)
        # self.timer.cancel()   # é possível cancelar o timer chamando esse método; esta linha é só um exemplo e pode ser removida

    def _exemplo_timer(self, callback, dados):
        # Esta função é só um exemplo e pode ser removida
        print('Este é um exemplo de como fazer um timer')

    def _rdt_rcv(self, seq_no, ack_no, flags, payload):
        
        # TODO: trate aqui o recebimento de segmentos provenientes da camada de rede.
        src_addr, src_port, dst_addr, dst_port = self.id_conexao
        #print("SEQ_NO ESPERADO: " +str(self.expected_seq_no))
        #print(seq_no, ack_no, flags, len(payload))

        if(seq_no == self.expected_seq_no):
            self.expected_seq_no = seq_no + len(payload)
        # Chame self.callback(self, dados) para passar dados para a camada de aplicação após 
            new_segment = fix_checksum(make_header(src_port, dst_port, ack_no ,seq_no + len(payload), FLAGS_ACK),src_addr,dst_addr)
            self.callback(self, payload)
            self.servidor.rede.enviar(new_segment,dst_addr)

        # garantir que eles não sejam duplicados e que tenham sido recebidos em ordem.
           # print('recebido payload: %r' % payload)

    # Os métodos abaixo fazem parte da API

    def registrar_recebedor(self, callback):
        """
        Usado pela camada de aplicação para registrar uma função para ser chamada
        sempre que dados forem corretamente recebidos
        """
        self.callback = callback

    def enviar(self, dados):
        """
        Usado pela camada de aplicação para enviar dados
        """
        #print(len(dados))
        src_addr, src_port, dst_addr, dst_port = self.id_conexao
        new_segment = fix_checksum(make_header(src_port,dst_port,self.seq_no+1,self.expected_seq_no,FLAGS_ACK) + dados,src_addr,dst_addr)
        # TODO: implemente aqui o envio de dados.
        self.expected_seq_no += len(dados)
        self.servidor.rede.enviar(new_segment, dst_addr)
        # Chame self.servidor.rede.enviar(segmento, dest_addr) para enviar o segmento
        # que você construir para a camada de rede.
        pass

    def fechar(self):
        """
        Usado pela camada de aplicação para fechar a conexão
        """
        # TODO: implemente aqui o fechamento de conexão
        src_addr, src_port, dst_addr, dst_port = self.id_conexao
        new_segment = make_header(
            src_port, dst_port, self.seq_no, 1, FLAGS_FIN)
        FIN_dados = [new_segment, src_addr]
        self.enviar(FIN_dados)
        self.servidor.kill_conexao(self)