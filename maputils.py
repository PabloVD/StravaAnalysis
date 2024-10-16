import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from geopandas.tools import sjoin
import folium
from folium.plugins import Geocoder, Draw


def create_popup(name,dist,time,elevation,date):
    
    popup = "<b>"+ name +"</b>"
    popup += "<ul><li>"+str(pd.to_datetime(date))+"</li><li>Distance:&nbsp;{:.2f}&nbsp;km</li><li>Elevation:&nbsp;{:.0f}&nbsp;m</ul>".format(dist,elevation)
    
    return popup

def create_map(data_acts, data_names, municipis_data):
    
    mean_lat, mean_lon = tuple(np.median(np.array([np.median(data[['lat', 'long']].to_numpy(),0) for data in data_acts]),0))

    # Get more tilesets from https://leaflet-extras.github.io/leaflet-providers/preview/

    # Default tileset
    tileset = 'https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png'
    attr = '<a href="https://github.com/cyclosm/cyclosm-cartocss-style/releases" title="CyclOSM - Open Bicycle render">CyclOSM</a> | Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

    route_map = folium.Map(
        location=[mean_lat, mean_lon],
        zoom_start=12,
        tiles=folium.TileLayer(tiles=tileset,attr=attr,name="CyclOSM"),
        tooltip = 'This tooltip will appear on hover'
        #width=1024,
        #height=600
    )

    # Add more optional tilesets
    folium.TileLayer("OpenStreetMap",name="OpenStreetMap").add_to(route_map)
    tileset = "http://tile.mtbmap.cz/mtbmap_tiles/{z}/{x}/{y}.png"
    attr = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &amp; USGS'
    folium.TileLayer(tiles=tileset,attr=attr,name="MtbMap").add_to(route_map)
    folium.TileLayer("Stamen Terrain",name="Stamen Terrain").add_to(route_map)
    tileset = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
    attr = 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
    folium.TileLayer(tiles=tileset,attr=attr,name="Esri.WorldImagery").add_to(route_map)

    rutas = folium.FeatureGroup(name='Rutes').add_to(route_map)

    for i, data in enumerate(data_acts):
        coordinates = [tuple(x) for x in data[['lat', 'long']].to_numpy()]
        popup = create_popup(data_names.iloc[i]["name"],data_names.iloc[i]["distance"],data_names.iloc[i]["moving_time"],data_names.iloc[i]["elevation"],data_names.iloc[i]["start_time"])
        folium.PolyLine(coordinates, weight=2, color= 'red', opacity=0.7, popup=popup).add_to(rutas)

    # Include municipilaties
    folium.GeoJson(data=municipis_data["geometry"],name="Municipis",show=False).add_to(route_map)

    Draw(export=False).add_to(route_map)

    Geocoder().add_to(route_map)

    folium.LayerControl().add_to(route_map)
    folium.plugins.Fullscreen(
        position="topright",
        title="Expand me",
        title_cancel="Exit me",
        force_separate_button=True,
    ).add_to(route_map)
    
    route_map.save("htmls/route_map.html")
    
    return route_map
 
# Get regions which contain route points
def get_covered_regions(coordinates):

    # Load the GeoJSON file with region boundaries
    geo_df = gpd.read_file('data/Municipios_IGN.geojson')

    # Create a GeoSeries of Shapely Point objects from the array of coordinates
    points = gpd.GeoSeries([Point(xy[1],xy[0]) for xy in coordinates])

    # Ensure the CRS (Coordinate Reference System) is the same for both datasets
    points_gdf = gpd.GeoDataFrame(geometry=points, crs=geo_df.crs)

    # Perform a spatial join to find which points fall within which regions
    # Ensure both GeoDataFrames have geometries and the correct CRS
    joined = sjoin(geo_df, points_gdf, how="inner", predicate='contains')

    # Drop duplicate region entries (because multiple points may fall in the same region)
    regions_with_points = geo_df.loc[joined.index.unique()]

    return regions_with_points