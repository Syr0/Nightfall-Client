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
        for name in table_names:
            print(name)

        if not table_names:
            print("No tables found.")
        else:
            example_table = table_names[0]
            print(f"\nColumns in '{example_table}':")

            columns = cursor.columns(table=example_table)
            for column in columns:
                print(f"{column.column_name} ({column.type_name})")


        conn.close()
    except Exception as e:
        print(f"Error connecting to database: {e}")