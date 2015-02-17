#!/usr/bin/python3.4
import requests, sys, matplotlib, datetime, os.path, json, numpy

database_url = 'http://localhost:5984/tracked_steam_item_stats/'
document_name = '2015-02-12 19:45:12.022684'


def import_graph_json():
	#Holds steam market item data, including graph data-points.
	market_data_request = None 
	market_data_json = None

	#Check for cached data
	if os.path.isfile('graph-data-cache.json'):
		print("Reading cached data...")
		cache = open('graph-data-cache.json', 'r')
		market_data_json = json.loads(cache.read())
	else:
		#Request a document containing item graph data.
		print("Downloading data...")
		try: 
			market_data_request = requests.get(database_url + document_name)
			market_data_request.raise_for_status() #Raise exception if HTTP error occurred
		except Exception as http_exception: 
			print(http_exception) 
			sys.exit()

		#Convert response to JSON
		try: 
			market_data_json = market_data_request.json().get('steam_items') #convert request to json.
			cache = open('graph-data-cache.json', 'w')
			json.dump(market_data_json, cache)
		except Exception as parsing_exception:
			print(parsing_exception)
			sys.exit()

	return market_data_json

def json_to_points(data_json):
	from matplotlib.dates import date2num
	from datetime import datetime
	from collections import OrderedDict


	graph_data_aggregate = []

	for market_item in data_json:
		market_item_name = market_item.get('name')
		graph_points = market_item.get('graph_points')

		graph_points = OrderedDict(sorted(graph_points.items()))

		dates = []
		prices = []

		for date, price in graph_points.items():
			dates.append(datetime.strptime(date, "%Y-%m-%d %H:%M:%S"))
			prices.append(price)

		graph_data_aggregate.append({'name':market_item_name, 'prices':prices ,'dates':dates})

	return graph_data_aggregate

def poly_calc(graph_data, poly_degree=1):
	from matplotlib import pyplot
	from matplotlib.dates import date2num

	graph_data['dates'] = date2num(graph_data['dates'])
	#coefficients = numpy.polyfit(graph_data['dates'], graph_data['prices'], poly_degree)
	coefficients = numpy.polyfit(graph_data['dates'], graph_data['prices'], poly_degree, w=graph_data['prices'])
	polynomial = numpy.poly1d(coefficients)

	return polynomial

def poly_plot(graph_data, poly_degree=1, buy_price=None, sell_price=None):
	from matplotlib import pyplot
	from matplotlib.dates import date2num

	poly_y = graph_data['polynomial'](graph_data['dates'])
	pyplot.plot_date(graph_data['dates'], graph_data['prices'], 'o-')
	pyplot.plot_date(graph_data['dates'], poly_y, 'g-')
	if not buy_price is None:
		pyplot.axhline(y=buy_price, linewidth=1, color = 'k')
	if not sell_price is None:
		pyplot.axhline(y=sell_price, linewidth=1, color = 'k')
	pyplot.ylabel('y')
	pyplot.xlabel('x')
	pyplot.title(graph_data['name'])
	pyplot.show()

def search_graph_data(graph_data_aggregate, query=None, limit=30, profit_min=None):
	display_options = []

	if query is None: query = input('Search query: ')
	for graph_data in graph_data_aggregate:
		if query.lower() in graph_data['name'].lower():
			if not profit_min is None:
				if(graph_data['profit'] > profit_min):
					display_options.append(graph_data)
			else:
				display_options.append(graph_data)
	if(len(display_options) <= limit and len(display_options) > 0):
		count = 0
		item_name_max = 0
		for display_option in display_options:
			if len(display_option['name']) > item_name_max:
				item_name_max = len(display_option['name'])

		for display_option in display_options:
			output = ('[{:>2}] - {:<' + str(item_name_max) +  '} |  Profit: ${:>5} |  Percent: {:>4}%  ')\
			 .format(str(count), display_option['name'], display_option['profit'], display_option['profit_percent'])
			print(output)
			#print('[' + str(count) + ']' + ' - ' + display_option['name'])
			count += 1
		try: 
			selection = int(input('\nSelection: '))
		except Exception:
			print('Please enter an index.')
			return False
		if (selection + 1) > len(display_options) or selection < 0:
			print('Not in range.')
			return False
		else:
			return display_options[selection]
	else:
		print(str(len(display_options)) + ' matches found. Narrow query.')
		return False

def get_buy_sell(graph_data, m=1.7):
	from statistics import mean, stdev

	data_mean = mean(graph_data['prices'])
	stdev = stdev(graph_data['prices'])

	buy_price = data_mean - (stdev * m)
	sell_price = data_mean + (stdev * m)

	return buy_price, sell_price

#Anything which doesn't fit the standard model will be removed (mostly low price items)
def remove_non_standard_dev(graph_data_aggregate):
	graph_data_aggregate_trimmed = []

	for graph_data in graph_data_aggregate:
		if graph_data['buy_price'] > 0:
			graph_data_aggregate_trimmed.append(graph_data)
	return graph_data_aggregate_trimmed

#Needs fixing before deployment
def remove_outliers(graph_data_aggregate, m=2):
	from statistics import mean, stdev

	graph_data_aggregate_filtered = []
	#Isolate price data for preliminary mean and stdev calculation
	for graph_data in graph_data_aggregate:
		prices = []
		for price in graph_data['prices']:
			prices.append(price)

		data_mean = mean(prices)
		data_stdev = stdev(prices)
		good_data = []

		#Generate a new prices and dates list
		trimmed_prices = []
		trimmed_dates = []

		for price, date in zip(graph_data['prices'], graph_data['dates']):
			#if the distance from the mean is < 2x the stdev, keep the data
			if(abs(price - data_mean) < (m * data_stdev)):
				trimmed_prices.append(price)
				trimmed_dates.append(date)
		
		graph_data['prices'] = trimmed_prices
		graph_data['dates'] = trimmed_dates

		if(len(graph_data['prices']) > 0):
			graph_data_aggregate_filtered.append(graph_data)

	return graph_data_aggregate_filtered

#def get_buy_sell_prices(graph_data_aggregate, remove_outliers=True):
	
def calculate_profit(min_price, max_price):
	fees = round(min_price * 0.15, 2)
	profit = round(max_price - min_price - fees, 2)
	return profit

def calculate_percent_gain(buy_at, sell_at):
	profit = calculate_profit(buy_at, sell_at)
	return round(100 * (profit / ((buy_at + sell_at)) / 2), 1)

def convert_dates_to_ordered(graph_data_aggregate):
	from matplotlib.dates import date2num
	from collections import OrderedDict

	graph_data_aggregate_ordered = []
	#Create an array with date and price
	for graph_data in graph_data_aggregate:
		for date, price in zip(graph_data['dates'], graph_data['prices']):
		#graph_data_ordered = OrderedDict(sorted(graph_data.items(), key=lambda t: date2num(t['dates'])))
			dates_ordered = OrderedDict(sorted(graph_data, key=lambda k: 'dates'))
			graph_data_aggregate_ordered.append(graph_data_ordered)

	return graph_data_aggregate_ordered

def main():
	from datetime import timedelta

	market_data_json = import_graph_json()
	graph_data_aggregate = json_to_points(market_data_json)

	#graph_data_aggregate = filter_by_time_delta(graph_data_aggregate, timedelta(days=3))

	graph_data_aggregate = remove_outliers(graph_data_aggregate, m=2)
	#graph_data_aggregate = remove_outliers(graph_data_aggregate, m=2)

	#Run poly calc on all items in aggregate
	#for graph_data in graph_data_aggregate:

	#for graph_data in graph_date_aggregate_filtered:
	#	graph_data['polynomial'] = poly_calc(graph_data)

	for graph_data in graph_data_aggregate:
		buy_price, sell_price = get_buy_sell(graph_data, m=1.7)
		graph_data['buy_price'] = buy_price
		graph_data['sell_price'] = sell_price
		graph_data['polynomial'] = poly_calc(graph_data, poly_degree=2)
		graph_data['profit'] = calculate_profit(buy_price, sell_price)
		graph_data['profit_percent'] = calculate_percent_gain(buy_price, sell_price)

	graph_data_aggregate = remove_non_standard_dev(graph_data_aggregate)
	#graph_data_aggregate = convert_dates_to_ordered(graph_data_aggregate)

	#Sort with lambda function to select appropriate sorting key
	#graph_data_aggregate = sorted(graph_data_aggregate, key=lambda k: k['polynomial'][0])
	graph_data_aggregate = sorted(graph_data_aggregate, key=lambda k: k['profit_percent'], reverse=False)
	#graph_data_aggregate_filtered = sorted(graph_data_aggregate_filtered, key=lambda k: k['polynomial'][0]) 

	print('Index: 0-' + str(len(graph_data_aggregate) - 1))
	while True:
		search_request = search_graph_data(graph_data_aggregate, limit=1000)
		#print(graph_data_aggregate[search_request]['polynomial'])
		if not search_request is False:
			poly_plot(search_request, 1, buy_price=search_request['buy_price'], sell_price=search_request['sell_price'])
		#print(graph_data_aggregate_filtered[search_request]['polynomial'])
		#poly_plot(graph_data_aggregate_filtered[search_request], 1)

if __name__ == '__main__':
	main()