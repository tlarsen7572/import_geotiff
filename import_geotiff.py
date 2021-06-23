import AlteryxPythonSDK as Sdk
import xml.etree.ElementTree as Et
from PIL import Image
import math


class AyxPlugin:
    def __init__(self, n_tool_id: int, alteryx_engine: object, output_anchor_mgr: object):
        # Default properties
        self.n_tool_id: int = n_tool_id
        self.alteryx_engine: Sdk.AlteryxEngine = alteryx_engine
        self.output_anchor_mgr: Sdk.OutputAnchorManager = output_anchor_mgr
        self.label = "Import Geotiff"

        # Custom properties
        self.Filepath: str = None
        self.OutInfo: Sdk.RecordInfo = None
        self.TopLeft: Sdk.Field = None
        self.Row: Sdk.Field = None
        self.Column: Sdk.Field = None
        self.Lon: Sdk.Field = None
        self.Lat: Sdk.Field = None
        self.Elevation: Sdk.Field = None
        self.Output: Sdk.OutputAnchor = None
        self.Creator: Sdk.RecordCreator = None

        self.cell_start = 6
        self.cells_in_axis = 3600

    def pi_init(self, str_xml: str):
        xml_parser = Et.fromstring(str_xml)
        self.Filepath = xml_parser.find("Filepath").text if 'Filepath' in str_xml else ''

        # Getting the output anchor from Config.xml by the output connection name
        self.Output = self.output_anchor_mgr.get_output_anchor('Output')

    def pi_add_incoming_connection(self, str_type: str, str_name: str) -> object:
        raise NotImplementedError()

    def pi_add_outgoing_connection(self, str_name: str) -> bool:
        return True

    def pi_push_all_records(self, n_record_limit: int) -> bool:
        self.create_record_info()

        if self.alteryx_engine.get_init_var(self.n_tool_id, 'UpdateOnly') == 'True':
            self.Output.close()
            return True

        try:
            im = Image.open(self.Filepath)
            coords = im.tag_v2.get(33922)
            lon_start = float(math.trunc(coords[3]))
            lat_start = float(math.trunc(coords[4]))
            self.TopLeft.set_from_string(self.Creator, f'{int(lat_start)} {int(lon_start)}')

            if im.height != 3612 or im.width != 3612:
                self.display_error_msg(f"expected size of 3612x3612 and got {im.width}x{im.height}")
                return False

            start_coord = 1 / (self.cells_in_axis * 2.0)
            lon = lon_start + start_coord
            lat = lat_start - start_coord

            x, y = 0, 0
            while y < self.cells_in_axis:
                while x < self.cells_in_axis:
                    pixel = im.getpixel((x+self.cell_start, y+self.cell_start))
                    if pixel <= -9999.0:
                        pixel = 0.0
                    self.push_record(x+1, y+1, lon, lat, pixel)

                    x += 1
                    lon = lon_start + start_coord + (x / self.cells_in_axis)
                x = 0
                lon = lon_start + start_coord
                y += 1
                lat = lat_start - start_coord - (y / self.cells_in_axis)

            im.close()
            self.Output.close()
        except Exception as ex:
            self.display_error_msg(f'{ex}')
            return False

        return True

    def pi_close(self, b_has_errors: bool):
        return

    def display_error_msg(self, msg_string: str):
        self.alteryx_engine.output_message(self.n_tool_id, Sdk.EngineMessageType.error, msg_string)

    def display_info_msg(self, msg_string: str):
        self.alteryx_engine.output_message(self.n_tool_id, Sdk.EngineMessageType.info, msg_string)

    def create_record_info(self):
        self.OutInfo = Sdk.RecordInfo(self.alteryx_engine)
        self.TopLeft = self.OutInfo.add_field("Top Left", Sdk.FieldType.string, size=8)
        self.Row = self.OutInfo.add_field("Row", Sdk.FieldType.int32)
        self.Column = self.OutInfo.add_field("Column", Sdk.FieldType.int32)
        self.Lon = self.OutInfo.add_field("Lon", Sdk.FieldType.double)
        self.Lat = self.OutInfo.add_field("Lat", Sdk.FieldType.double)
        self.Elevation = self.OutInfo.add_field("Elevation", Sdk.FieldType.double)
        self.Creator = self.OutInfo.construct_record_creator()
        self.Output.init(self.OutInfo)

    def push_record(self, row, column, lon, lat, elevation):
        self.Creator.reset()
        self.Row.set_from_int64(self.Creator, row)
        self.Column.set_from_int64(self.Creator, column)
        self.Lon.set_from_double(self.Creator, lon)
        self.Lat.set_from_double(self.Creator, lat)
        self.Elevation.set_from_double(self.Creator, elevation)
        blob = self.Creator.finalize_record()
        self.Output.push_record(blob)
