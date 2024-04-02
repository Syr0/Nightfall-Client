import webbrowser
import pyodbc

def find_access_driver():
    for driver in pyodbc.drivers():
        if 'ACCESS' in driver.upper():
            return driver
    return None

db_file = r"C:\Program Files (x86)\zMUD\nightfall\Map\Map.mdb"

access_driver = find_access_driver()
if access_driver is None:
    print("Microsoft Access Driver not found.")
    print("Please download and install the 64-bit Microsoft Access Database Engine 2016 Redistributable.")
    print("Opening download page...")
    webbrowser.open("https://www.microsoft.com/en-us/download/details.aspx?id=54920")
else:
    print(f"Found driver: {access_driver}")
    conn_str = f'DRIVER={{{access_driver}}};DBQ={db_file}'

    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        tables = cursor.tables(tableType='TABLE')
        table_names = [table.table_name for table in tables]

        print("Found tables:")
        for table_name in table_names:
            print(table_name)

            # Fetching column names
            columns = cursor.columns(table=table_name)
            column_names = [column.column_name for column in columns]

            # Fetching data for each column
            for column_name in column_names:
                print(f"\tColumn: {column_name}")

                try:
                    # Fetching at least one row of data for the column
                    cursor.execute(f"SELECT TOP 1 [{column_name}] FROM [{table_name}]")
                    row = cursor.fetchone()

                    if row is not None:
                        print(f"\t\tExample data: {row[0]}")
                    else:
                        print("\t\tNo data available.")
                except Exception as e:
                    print(f"\t\tError fetching data: {e}")

        conn.close()
    except Exception as e:
        print(f"Error connecting to database: {e}")
