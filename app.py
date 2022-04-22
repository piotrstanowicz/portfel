import os, os.path
import random, string
from datetime import date
from dateutil.relativedelta import relativedelta
import pandas as pd
import cherrypy
from jinja2 import Environment, FileSystemLoader


env = Environment(loader=FileSystemLoader('.'))
finst = pd.read_csv('finst.csv', index_col='code')                                                                                              # financial instruments


class Portfel:
    @cherrypy.expose
    def index(self, **params):
        # variables
        session_id = cherrypy.session.setdefault('id', ''.join(random.sample(string.hexdigits, int(8))))                                        # session id
        begin_date = params.setdefault('begin', (date.today() - relativedelta(years=3)).strftime('%Y-%m-%d'))                                   # begin date
        end_date = params.setdefault('end', date.today().strftime('%Y-%m-%d'))                                                                  # end date
        delta = date(*map(int, end_date.split('-'))) - date(*map(int, begin_date.split('-')))                                                   # number of days
        for i in finst.index[finst['type'] == 'fund']:
            params.setdefault(i, int(finst.at[i, 'default']))
        for i in finst.index[finst['type'] == 'index']:
            params.setdefault(i, finst.at[i, 'default'])

        # quotation database
        quotes = pd.read_csv('quotes.csv', index_col='Data')                                                                                    # read data from file

        quotes['WIBOR6M'] = 100                                                                                                                 # calculate WIBOR6M
        for i in range(1, len(quotes)):
            quotes['WIBOR6M'].iat[i] = quotes['WIBOR6M'].iat[i-1] * ((quotes['WIBOR6M_rate'].iat[i] / 36000) + 1)

        quotes['Portfel'] = sum(list(map(lambda x: int(params[x]) / 100 * quotes[x], finst.index[finst['type'] == 'fund'])))                    # calculate Portfel

        normalised = quotes[(quotes.index.values >= begin_date) & (quotes.index.values <= end_date)]                                            # filter by dates
        normalised = normalised.div(normalised.iloc[0]) * 100                                                                                   # normalize

        annual = pd.DataFrame({'Data': normalised.index}).set_index('Data')                                                                     # annual returns on investment
        for i in normalised.columns:
            for j in annual.index:
                k = (date(*map(int, j.split('-'))) - relativedelta(years=1)).strftime('%Y-%m-%d')
                annual.at[j, i] = quotes.at[j, i] / quotes.at[k, i] - 1

        # graph
        normalised.plot(kind='line', y=[i for i in finst.index[finst['type'] == 'index'] if params[i] == 'on'],
            figsize=(10, 6), grid=True).get_figure().savefig(f'public/{session_id}.png')                                                        # generate png image

        # table
        table = finst.loc[(finst['type'].isin(['fund', 'index'])), ['name', 'type']]                                                            # code and name columns
        table = table.join(normalised.tail(1).T.add(-100).rename(columns={normalised.index[-1]: 'roi'}))                                        # roi from last quotation
        table['roi_pa'] = table['roi'] / delta.days * 365                                                                                       # roi p.a.
        for i in table.index:
            table.at[i, 'std_p'] = annual[i].std(ddof=0) * 100
            table.at[i, 'min'] = annual[i].min() * 100
            table.at[i, 'median'] = annual[i].median() * 100
            table.at[i, 'max'] = annual[i].max() * 100
        # for i in range(2, len(table.columns)):
        #     table.iloc[:, [i]] = table.iloc[:, [i]].map('{:,.2f}%'.format)
        table['roi'] = table['roi'].map('{:,.2f}%'.format)                                                                                      # roi format
        table['roi_pa'] = table['roi_pa'].map('{:,.2f}%'.format)                                                                                # roi p.a. format
        table['std_p'] = table['std_p'].map('{:,.2f}%'.format)                                                                                  # roi p.a. format
        table['min'] = table['min'].map('{:,.2f}%'.format)                                                                                      # roi p.a. format
        table['median'] = table['median'].map('{:,.2f}%'.format)                                                                                # roi p.a. format
        table['max'] = table['max'].map('{:,.2f}%'.format)                                                                                      # roi p.a. format

        table.to_csv('table.csv')

        # template
        tmpl = env.get_template('template.html')
        return tmpl.render(params=params, funds=table.reset_index().to_dict('records'), id=session_id)

    @cherrypy.expose
    def aktualizuj(self):
        begin_date = '20150102'                                                                                                                 # cut-off dates
        end_date = date.today().strftime("%Y%m%d")

        quotes = pd.DataFrame({'Data': [d.strftime('%Y-%m-%d') for d in pd.date_range(start=begin_date, end=end_date)]}).set_index('Data')      # dataframe of dates

        for i in finst.index:                                                                                                                   # join fin.instruments quotes
            if pd.notna(finst['url'][i]):
                quotes = quotes.join(pd.read_csv(f"https://stooq.pl/q/d/l/?s={finst['url'][i]}&d1={begin_date}&d2={end_date}&i=d",
                    index_col='Data').loc[:, ['Zamkniecie']].rename(columns={'Zamkniecie': i}))

        quotes.fillna(method='ffill').to_csv('quotes.csv')                                                                                      # fill gaps & save to file

        return 'Gotowe<p><a href="/">Powrót</a>'


if __name__ == '__main__':
    cherrypy.config.update({'server.socket_host': '0.0.0.0'})
    cherrypy.quickstart(Portfel(), '/', {
        '/': {
            'tools.sessions.on': True,
            'tools.staticdir.root': os.path.abspath(os.getcwd())
        },
        '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': './public'
        }
    })
