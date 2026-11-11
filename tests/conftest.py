"""Os testes esperam a interface em português, qualquer que seja o idioma do sistema da máquina de CI
(o padrão da v1.7.1 é seguir o idioma do sistema). Vale também para os testes em subprocesso, que herdam o ambiente."""
import os

os.environ.setdefault("PT2VHF_LANG", "pt-BR")
