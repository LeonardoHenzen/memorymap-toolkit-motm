Function for extracting data from "metadata" file format

File code: xlsx_person_readr.py
    Procedure: read_raw_person_sheet(xlsx_path, sheet_name=None) 
            Raw reading from xlsx file and field extraction.
    Procedure: read_person_record(xlsx_path, write_json=False)
            Person data extraction from file (using read_raw_person_sheet)

Launch: (from code or ) from
 $ docker compose exec memorymaptoolkit bash
 /app$ python manage.py shell
    run: from mmt_motm.importers.xlsx_person_reader import read_person_record
         record = read_person_record("data/metadati_nameNN.xlsx", write_json=True)