from silverlabnwb import NwbFile
import os

if __name__ == '__main__':
    for subdirs in os.walk("C:\\Users\\Alessandro\\Documents\\UCL-projects\\silverlab\\Data\\"):
        if subdirs[0].endswith('FunctAcq'):
            import_folder_name = subdirs[0].split("\\")[-1]
            print("writing "+import_folder_name)
            with NwbFile("C:\\Users\\Alessandro\\Documents\\UCL-projects\\silverlab\\Data\\by-pysilverlab\\"+import_folder_name+"-by-pysilverlab.nwb", mode='w') as nwb:
                nwb.import_labview_folder(subdirs[0])
