"""Generate PT2VHF SAT TOOL icon assets, fully offline, for Windows executables.

Pillow rasterizes a matching vector-style mark at high resolution. Generated
ICO is embedded in both PyInstaller flavors and the Inno Setup installer.
"""
from pathlib import Path
from math import cos, sin, radians
from PIL import Image, ImageDraw


def build(output=None):
    root = output or (Path(__file__).resolve().parents[1] / "assets" / "branding")
    root.mkdir(parents=True, exist_ok=True)
    size = 1024
    im = Image.new("RGBA", (size,size), (0,0,0,0))
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle((14,14,1010,1010),radius=208,fill=(7,24,45,255),outline=(28,153,195,255),width=14)
    for radius,opacity in [(305,38),(244,28),(190,17)]:
        draw.ellipse((512-radius,586-radius,512+radius,586+radius),outline=(63,183,232,opacity),width=12)
    draw.ellipse((269,358,755,844),fill=(22,77,118,255),outline=(70,214,236,255),width=17)
    draw.polygon([(294,575),(363,518),(439,540),(449,627),(399,695),(360,718),(310,668)],fill=(54,150,158,255))
    draw.polygon([(535,409),(618,433),(682,504),(645,561),(574,533)],fill=(54,155,154,255))
    draw.arc((156,342,870,811),start=189,end=355,fill=(25,202,249,255),width=25)
    draw.arc((157,342,870,811),start=1,end=172,fill=(25,202,249,255),width=25)
    draw.arc((158,351,867,796),start=175,end=185,fill=(25,202,249,255),width=20)
    # Spacecraft: panel, central body, two antennas.
    draw.line((735,257,735,153),fill=(219,246,255,255),width=11)
    draw.line((758,316,835,387),fill=(219,246,255,255),width=10)
    draw.polygon([(735,191),(808,232),(762,313),(694,276)],fill=(211,241,255,255),outline=(24,203,255,255))
    draw.polygon([(553,134),(675,195),(629,283),(507,221)],fill=(32,137,204,255))
    draw.polygon([(819,263),(940,322),(894,413),(773,350)],fill=(32,137,204,255))
    for off in (0,49):
        draw.line((554+off,136+off//2,506+off,222+off//2),fill=(153,237,255,255),width=7)
        draw.line((820+off,264+off//2,772+off,351+off//2),fill=(153,237,255,255),width=7)
    for rad in (156,108,60):
        draw.arc((115-rad/2,170-rad/2,115+rad,170+rad),start=280,end=355,fill=(31,220,250,255),width=19)
    draw.ellipse((467,697,492,722),fill=(247,215,88,255))
    draw.ellipse((468,697,492,721),outline=(255,255,255,255),width=5)
    for size_out in (16,24,32,48,64,128,256,512,1024):
        im.resize((size_out,size_out),Image.Resampling.LANCZOS).save(root/("icon-%d.png"%size_out))
    im.save(root/"app-icon.ico",format="ICO",sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
    assert (root/"app-icon.ico").stat().st_size > 3000
    return root


if __name__=="__main__":
    result=build()
    print("Logo assets OK:",result)
