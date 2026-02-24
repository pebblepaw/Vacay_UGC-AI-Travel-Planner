import math
from typing import List
from backend.models.schemas import POI, Trip, Day

class RouteOptimizer: 
    @staticmethod 
    def calculate_distance(coord1: tuple, coord2: tuple) -> float: 
        # Euclidean distance
        return math.sqrt(pow(coord2[0] - coord1[0], 2) 
                        + pow(coord2[1] - coord1[1], 2))

    @staticmethod
    def optimize_day(day_pois: List[POI]) -> List[POI]: 

        # O(N^2) complexity, good enough for <20 items
        if not day_pois: 
            return [] 

        # Start at first POI (usually most important)

        optimised = [day_pois[0]]
        remaining = day_pois[1:]

        while remaining: 
            last_stop = optimised[-1]
            
            # loop through, find next closest spot and so on
            next_stop = min(
                remaining, 
                key = lambda p: 
                RouteOptimizer.calculate_distance(
                    last_stop.coords,p.coords)
                )
            
            optimised.append(next_stop)
            remaining.remove(next_stop)

        return optimised

    @staticmethod
    def optimize_trip(trip: Trip) -> Trip: 

        # loop through each day, optimize route
        for day in trip.days: 
            day.pois = RouteOptimizer.optimize_day(day.pois)

        return trip 

route_optimizer = RouteOptimizer() 
            



        

