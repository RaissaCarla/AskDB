
from app.sql_executor import executar_consulta_segura

sql = "DROP TABLE clientes"

try:
    resultado = executar_consulta_segura(sql)
    print("ATENÇÃO: comando aceito!", resultado)
except ValueError as erro:
    print("Bloqueio esperado:", erro)
