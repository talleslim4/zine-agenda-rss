# Feed RSS da agenda do Zine Cultural

Este projeto busca a agenda diretamente no Zine Cultural, percorre os links de paginação encontrados e gera um RSS 2.0. A lista de eventos não fica hardcoded: o script consulta o site sempre que é executado.

## Publicar gratuitamente com GitHub

A combinação GitHub Actions + GitHub Pages executa o scraper periodicamente e hospeda o XML em uma URL pública. Para usar o plano gratuito, crie um repositório **público** no GitHub e envie estes arquivos mantendo a estrutura:

- `zine_agenda_rss.py`
- `requirements.txt`
- `.github/workflows/update-feed.yml`
- `docs/feed.xml` (opcional; o workflow gera uma versão nova ao publicar)

Depois, no repositório, abra **Settings → Pages** e selecione **GitHub Actions** como fonte de publicação. Na aba **Actions**, execute uma vez o workflow **Atualizar feed RSS** pelo botão **Run workflow**. O feed ficará neste formato:

```text
https://SEU-USUARIO.github.io/NOME-DO-REPOSITORIO/feed.xml
```

O workflow agenda uma nova consulta a cada hora, no minuto 17 UTC, e também pode ser executado manualmente. A atualização pode atrasar ocasionalmente na fila do GitHub. O repositório deve permanecer público para usar Pages e runners padrão sem custo no plano Free; isso também significa que o código e o feed serão públicos.

## Testar localmente

Com Python 3 instalado, execute:

```bash
pip install -r requirements.txt
python3 zine_agenda_rss.py --output docs/feed.xml
```

Para filtrar ainda mais os cartões pelo texto do local, acrescente `--only-city "Juiz de Fora"`. O padrão conserva todos os eventos retornados pelas páginas ligadas à URL informada.

## Como funciona

O script começa na URL enviada, segue os links numerados e anterior/próximo da paginação, e remove duplicatas pelo link de cada evento. O workflow roda esse processo novamente a cada hora e publica o XML atualizado. A geração observada no teste encontrou 42 eventos em cinco URLs de paginação, com duplicatas removidas.

O GitHub pode atrasar execuções agendadas em períodos de alta demanda e pode desativar workflows agendados em repositórios públicos após 60 dias sem atividade no repositório. Se isso ocorrer, basta reativar ou executar manualmente o workflow.
