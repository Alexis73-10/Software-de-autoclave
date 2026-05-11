from autoclave.hal import converters

def test_converters_realistic():
    data = [0, 1024, 2048, 3072, 4095, 2000, 3000, 1000,
            0, 512, 1024, 2048, 3072, 4095, 3500, 100]
    
    temps = converters.convert_temperatures(data, {})
    press = converters.convert_pressures(data, {})

    print("\n🌡️  Temperaturas:", temps)
    print("⛽  Presiones:", press)
    assert len(temps) == 8
    assert len(press) == 8

