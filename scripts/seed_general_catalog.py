"""Create bounded, sourced reference data. No prices or inventory are fabricated."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
old = json.loads((root / "data/catalog.json").read_text(encoding="utf-8"))
parts = []
for item in old:
    source = next(e["url"] for e in item["evidence"] if e["kind"] == "official")
    facts = {}
    for field, unit in (("logic_voltage_v", "V"), ("io_input_max_v", "V")):
        if item.get(field) is not None:
            facts[field] = {"value": item[field], "unit": unit, "source_url": source, "status": "source_checked", "scope": "输出额定电平" if field == "logic_voltage_v" else "厂商I/O耐受声明；具体引脚例外仍需核对"}
    facts["interfaces"] = {"value": item["interfaces"], "unit": "", "source_url": source, "status": "source_checked", "scope": "板级接口；不保证所有引脚同时可用"}
    parts.append({"id": item["id"], "name": item["name"], "mpn": item["name"].split("（")[0], "manufacturer": item["vendor"],
                  "category": "compute" if item["id"] == "raspberry-pi-5" else "vision", "kind": "board", "facts": facts,
                  "source_url": source, "notes": item["caveats"], "capabilities": item["capabilities"], "accessed_at": "2026-10-24"})


def fact(value, unit, url, scope="已读取厂商产品资料；未做实物测试"):
    return {"value": value, "unit": unit, "source_url": url, "status": "source_checked", "scope": scope}


u = "https://docs.arduino.cc/hardware/uno-rev3/"
parts.append({"id":"arduino-uno-r3","name":"Arduino UNO R3","mpn":"UNO R3","manufacturer":"Arduino","category":"controller","kind":"board","source_url":u,"accessed_at":"2026-10-24","capabilities":["mcu","pwm","adc"],"facts":{"clock_mhz":fact(16,"MHz",u),"digital_pins":fact(14,"",u),"analog_inputs":fact(6,"",u)},"notes":["基于ATmega328P；未将芯片引脚能力推定为全部板级连接可用。","本轮只录入已读取的官方参数，未核验的电平与整机功耗保持未知。"]})
u="https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html"
parts.append({"id":"esp32-devkitc-v4","name":"ESP32-DevKitC V4","mpn":"ESP32-DevKitC V4","manufacturer":"Espressif","category":"controller","kind":"board","source_url":u,"accessed_at":"2026-10-24","capabilities":["mcu","wifi","bluetooth"],"facts":{},"notes":["官方开发板指南已读取；模块/板卡修订版与可用GPIO需按实物核对。","USB供电与GPIO耐压分开，未用3V3电源引脚推定所有信号阈值。"]})
u="https://www.bosch-sensortec.com/en/products/environmental-sensors/humidity-sensors-bme280"
parts.append({"id":"bosch-bme280","name":"Bosch BME280 裸传感器IC","mpn":"BME280","manufacturer":"Bosch Sensortec","category":"sensor","kind":"ic","source_url":u,"accessed_at":"2026-10-24","capabilities":["temperature","humidity","pressure"],"facts":{"supply_min_v":fact(1.71,"V",u),"supply_max_v":fact(3.6,"V",u),"io_supply_min_v":fact(1.2,"V",u),"io_supply_max_v":fact(3.6,"V",u),"interfaces":fact(["I2C","SPI"],"",u)},"notes":["这是裸IC，不是带稳压/电平转换的第三方模块。","第三方BME280模块需单独核对原理图、套装和引出接口。"]})
u="https://www.ti.com/product/LM2596"
parts.append({"id":"ti-lm2596-adj","name":"TI LM2596 可调降压芯片","mpn":"LM2596-ADJ","manufacturer":"Texas Instruments","category":"power","kind":"ic","source_url":u,"accessed_at":"2026-10-24","capabilities":["buck"],"facts":{"supply_min_v":fact(4.5,"V",u),"supply_max_v":fact(40,"V",u)},"notes":["芯片需电感、电容、二极管等外围；不能当完整模块。","3A为厂商器件规格，实际持续输出受散热、外围与工况影响，不预填为整套电源保证值。"]})
parts.append({"id":"ti-lm2596-evm","name":"TI LM2596S-ADJEVM 评估模块","mpn":"LM2596S-ADJEVM","manufacturer":"Texas Instruments","category":"power","kind":"module","source_url":u,"accessed_at":"2026-10-24","capabilities":["buck","regulated_5v"],"facts":{"supply_min_v":fact(7,"V",u,"该EVM段落；不能移用于任意廉价模块"),"supply_max_v":fact(40,"V",u,"EVM输入范围"),"output_voltage_v":fact(5,"V",u,"EVM输出说明；需实测验证" )},"notes":["这是指定厂商EVM，不是淘宝任意LM2596模块的统一规格。","价格/库存/交期未预填。"]})
(root / "data/hardware_catalog.json").write_text(json.dumps(parts,ensure_ascii=False,indent=2),encoding="utf-8")
print(f"Wrote {len(parts)} sourced reference parts; custom parts remain extensible.")
