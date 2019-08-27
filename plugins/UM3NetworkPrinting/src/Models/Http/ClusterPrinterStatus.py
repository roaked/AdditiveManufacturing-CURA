# Copyright (c) 2019 Ultimaker B.V.
# Cura is released under the terms of the LGPLv3 or higher.
from itertools import product
from typing import List, Union, Dict, Optional, Any

from PyQt5.QtCore import QUrl

from cura.PrinterOutput.Models.PrinterConfigurationModel import PrinterConfigurationModel
from cura.PrinterOutput.PrinterOutputController import PrinterOutputController
from cura.PrinterOutput.Models.PrinterOutputModel import PrinterOutputModel

from .ClusterBuildPlate import ClusterBuildPlate
from .ClusterPrintCoreConfiguration import ClusterPrintCoreConfiguration
from .ClusterPrinterMaterialStation import ClusterPrinterMaterialStation
from .ClusterPrinterMaterialStationSlot import ClusterPrinterMaterialStationSlot
from ..BaseModel import BaseModel


##  Class representing a cluster printer
class ClusterPrinterStatus(BaseModel):

    ## Creates a new cluster printer status
    #  \param enabled: A printer can be disabled if it should not receive new jobs. By default every printer is enabled.
    #  \param firmware_version: Firmware version installed on the printer. Can differ for each printer in a cluster.
    #  \param friendly_name: Human readable name of the printer. Can be used for identification purposes.
    #  \param ip_address: The IP address of the printer in the local network.
    #  \param machine_variant: The type of printer. Can be 'Ultimaker 3' or 'Ultimaker 3ext'.
    #  \param status: The status of the printer.
    #  \param unique_name: The unique name of the printer in the network.
    #  \param uuid: The unique ID of the printer, also known as GUID.
    #  \param configuration: The active print core configurations of this printer.
    #  \param reserved_by: A printer can be claimed by a specific print job.
    #  \param maintenance_required: Indicates if maintenance is necessary.
    #  \param firmware_update_status: Whether the printer's firmware is up-to-date, value is one of: "up_to_date",
    #         "pending_update", "update_available", "update_in_progress", "update_failed", "update_impossible".
    #  \param latest_available_firmware: The version of the latest firmware that is available.
    #  \param build_plate: The build plate that is on the printer.
    #  \param material_station: The material station that is on the printer.
    def __init__(self, enabled: bool, firmware_version: str, friendly_name: str, ip_address: str, machine_variant: str,
                 status: str, unique_name: str, uuid: str,
                 configuration: List[Union[Dict[str, Any], ClusterPrintCoreConfiguration]],
                 reserved_by: Optional[str] = None, maintenance_required: Optional[bool] = None,
                 firmware_update_status: Optional[str] = None, latest_available_firmware: Optional[str] = None,
                 build_plate: Union[Dict[str, Any], ClusterBuildPlate] = None,
                 material_station: Union[Dict[str, Any], ClusterPrinterMaterialStation] = None, **kwargs) -> None:

        self.configuration = self.parseModels(ClusterPrintCoreConfiguration, configuration)
        self.enabled = enabled
        self.firmware_version = firmware_version
        self.friendly_name = friendly_name
        self.ip_address = ip_address
        self.machine_variant = machine_variant
        self.status = status
        self.unique_name = unique_name
        self.uuid = uuid
        self.reserved_by = reserved_by
        self.maintenance_required = maintenance_required
        self.firmware_update_status = firmware_update_status
        self.latest_available_firmware = latest_available_firmware
        self.build_plate = self.parseModel(ClusterBuildPlate, build_plate) if build_plate else None
        self.material_station = self.parseModel(ClusterPrinterMaterialStation,
                                                material_station) if material_station else None
        super().__init__(**kwargs)

    ## Creates a new output model.
    #  \param controller - The controller of the model.
    def createOutputModel(self, controller: PrinterOutputController) -> PrinterOutputModel:
        model = PrinterOutputModel(controller, len(self.configuration), firmware_version = self.firmware_version)
        self.updateOutputModel(model)
        return model

    ## Updates the given output model.
    #  \param model - The output model to update.
    def updateOutputModel(self, model: PrinterOutputModel) -> None:
        model.updateKey(self.uuid)
        model.updateName(self.friendly_name)
        model.updateType(self.machine_variant)
        model.updateState(self.status if self.enabled else "disabled")
        model.updateBuildplate(self.build_plate.type if self.build_plate else "glass")
        model.setCameraUrl(QUrl("http://{}:8080/?action=stream".format(self.ip_address)))

        # Set the possible configurations based on whether a Material Station is present or not.
        if self.material_station is not None and len(self.material_station.material_slots):
            self._updateAvailableConfigurations(model)
        if self.configuration is not None:
            self._updateActiveConfiguration(model)

    def _updateActiveConfiguration(self, model: PrinterOutputModel) -> None:
        configurations = zip(self.configuration, model.extruders, model.printerConfiguration.extruderConfigurations)
        for configuration, extruder_output, extruder_config in configurations:
            configuration.updateOutputModel(extruder_output)
            configuration.updateConfigurationModel(extruder_config)

    def _updateAvailableConfigurations(self, model: PrinterOutputModel) -> None:
        # Generate a list of configurations for the left extruder.
        left_configurations = [slot for slot in self.material_station.material_slots if self._isSupportedConfiguration(
            slot = slot,
            extruder_index = 0
        )]
        # Generate a list of configurations for the right extruder.
        right_configurations = [slot for slot in self.material_station.material_slots if self._isSupportedConfiguration(
            slot = slot,
            extruder_index = 1
        )]
        # Create a list of all available combinations between both print cores.
        available_configurations = [self._createAvailableConfigurationFromPrinterConfiguration(
            left_slot = left_slot,
            right_slot = right_slot,
            printer_configuration = model.printerConfiguration
        ) for left_slot, right_slot in product(left_configurations, right_configurations)]
        # Let Cura know which available configurations there are.
        model.setAvailableConfigurations(available_configurations)

    ## Check if a configuration is supported in order to make it selectable by the user.
    #  We filter out any slot that is not supported by the extruder index, print core type or if the material is empty.
    @staticmethod
    def _isSupportedConfiguration(slot: ClusterPrinterMaterialStationSlot, extruder_index: int) -> bool:
        return slot.extruder_index == extruder_index and slot.compatible and slot.material and \
               slot.material_remaining != 0

    @staticmethod
    def _createAvailableConfigurationFromPrinterConfiguration(left_slot: ClusterPrinterMaterialStationSlot,
                                                              right_slot: ClusterPrinterMaterialStationSlot,
                                                              printer_configuration: PrinterConfigurationModel
                                                              ) -> PrinterConfigurationModel:
        available_configuration = PrinterConfigurationModel()
        available_configuration.setExtruderConfigurations([left_slot.createConfigurationModel(),
                                                           right_slot.createConfigurationModel()])
        available_configuration.setPrinterType(printer_configuration.printerType)
        available_configuration.setBuildplateConfiguration(printer_configuration.buildplateConfiguration)
        return available_configuration