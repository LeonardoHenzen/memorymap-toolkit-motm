Function for extracting data from "metadata" and "chronotopoi" file format

File code: xlsx_person_reader.py
    Procedure: read_raw_person_sheet(xlsx_path, sheet_name=None) 
            Raw reading from xlsx file and field extraction.
    Procedure: read_person_record(xlsx_path, write_json=False)
            Person data extraction from file (using read_raw_person_sheet)

File code: xlsx_event_reader.py
    Procedure: read_raw_person_sheet(input_dir="data/eventi",output_dir="data/eventi/parsed") 
            Event and location data extraction from file *.xlsx (using chronotopoi)

Function for loading on DB data from "metadata" and "chronotopoi" json file
File code: db_import.py
    Procedure: import_all(directory="data/parsed")
        Import Person in DB from parsed json file
    Procedure: import_events_file("data/eventi/parsed/xy.events.json",
           "data/eventi/parsed/locations.json")
        Import Event in DB from parsed json file (event and location)

Launch example: (directly from code or ) from
 $ docker compose exec memorymaptoolkit bash
 /app$ python manage.py shell
    run: from mmt_motm.importers.xlsx_person_reader import read_person_record
         record = read_person_record("data/metadati_nameNN.xlsx", write_json=True)

Function export geodata from DB and import on MemoryMapper
    Procedure: export_geojson(identifiers=None):
        Extraction of geodata in json format from DB (None=All,PersonId,[list of id])
    run: from view localhost:8000/geojson/

    Procedure: sync_to_mm(identifiers=None)
        Importing geodata in MM (Theme, Points,Lines) using export_geojson
    run: directly from Admin/mmt_motm/Peolple