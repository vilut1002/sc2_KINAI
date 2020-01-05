
__author__ = '박현수 (hspark8312@ncsoft.com), NCSOFT Game AI Lab'

import random
from enum import Enum

import sc2
from sc2.position import Point2, Point3
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId

from IPython import embed


ARMY_TYPES = (UnitTypeId.MARINE, UnitTypeId.MARAUDER, 
    UnitTypeId.SIEGETANK, UnitTypeId.SIEGETANKSIEGED,
    UnitTypeId.MEDIVAC, UnitTypeId.AUTOTURRET)

# 주력부대에 속한 유닛 타입
#ARMY_TYPES = (UnitTypeId.MARINE, UnitTypeId.MARAUDER, 
#    UnitTypeId.SIEGETANK, UnitTypeId.SIEGETANKSIEGED,
#    UnitTypeId.MEDIVAC)

     
class StepManager(object):
    """
    스텝 레이트 유지를 담당하는 매니저
    """
    def __init__(self, bot_ai):
        self.bot = bot_ai
        self.seconds_per_step = 0.35714  # on_step이 호출되는 주기
        self.reset()
    
    def reset(self):
        self.step = -1
        # 마지막으로 on_step이 호출된 게임 시간
        self.last_game_time_step_evoked = 0.0 

    def invalid_step(self):
        """
        너무 빠르게 on_step이 호출되지 않았는지 검사
        """
        elapsed_time = self.bot.time - self.last_game_time_step_evoked
        if elapsed_time < self.seconds_per_step:
            return True
        else:
            # print(C.blue(f'man_step_time: {elapsed_time}'))
            self.step += 1
            self.last_game_time_step_evoked = self.bot.time
            return False


class StrategicManager(object):
    """
    Bot의 전략을 결정하는 매니저
    """
    def __init__(self, bot_ai):
        self.bot = bot_ai
        self.strategy = Strategy.NONE

    def reset(self):
        self.strategy = Strategy.HOLD
    
    def step(self):
        if self.bot.supply_cap>=100 and self.bot.supply_used>= 60 :
            self.strategy = Strategy.ATTACK
        elif self.bot.supply_cap >= 75:
            if self.bot.supply_used / (self.bot.supply_cap + 0.01) > 0.5:
                # 최대 보급량이 75이상이고, 
                # 최대 보급의 50% 이상을 사용했다면 병력이 준비된 것으로 판단
                # 공격전략 선택
                self.strategy = Strategy.ATTACK
            else:
            # else self.bot.supply_used / self.bot.supply_cap < 0.3:
            #     # 최대 보급의 0.3 밑이면 전선유지 전략 선택
                self.strategy = Strategy.HOLD
                global press_init
                press_init = False
        
        else:
            self.strategy = Strategy.HOLD

        """여기 코드 테스트는 못해보고 로직으로만 짰음
        enemy_tank_units = self.bot.known_enemy_units.filter(lambda u: u.tag in self.bot.known_enemy_units.tags).of_type(UnitTypeId.SIEGETANK)
        if 2<enemy_tank_units.closer_than(11, self.bot.terrein_manager.enemy_tank_point()).amount:   #탱크 드랍지점에 탱크가 3개 이상이면 드랍 시작
            self.bot.isTankDropTiming = True
        else :
            self.bot.isTankDropTiming = False
        """


        if self.bot.step_manager.step>300:
            self.strategy = Strategy.ATTACK
        else:
            self.strategy = Strategy.HOLD
            #적 탱크들마다
        #elif : 주력부대가 내 사령부에 와서 다 레디상태이면 기습공격 시작

        
    def debug(self):
        text = [
            f'Strategy: {self.strategy}',
            f'Supply used: {self.bot.supply_used / (self.bot.supply_cap + 0.01):1.3f}'
        ]
        self.bot._client.debug_text_screen(
            '\n\n'.join(text), pos=(0.02, 0.02), size=10)

class Strategy(Enum):
    """
    Bot이 선택할 수 있는 전략
    Strategy Manager는 언제나 이 중에 한가지 상태를 유지하고 있어야 함
    """
    NONE = 0
    ATTACK = 1
    HOLD = 2


#지형정보
class TerreinManager(object):
    """
    간단한 지형정보를 다루는 매니저
    """
    def __init__(self, bot_ai):
        self.bot = bot_ai
        # 자원이 생산되는 주요 전략적 요충지 좌표
        #  A     B
        #     C
        #  D     E
        self.strategic_points = [
            #        x   y   z
            Point3((28, 60, 12)),  # A 
            Point3((63, 65, 10)),  # B
            Point3((44, 44, 10)),  # C
            Point3((24, 22, 10)),  # D
            Point3((59, 27, 12)),  # E
        ]

        # 적 탱크 부수는 곳 좌표
        self.enemy_tank_points = [
            Point3((51, 36, 12)), # A꺼 
            Point3((36, 51, 12)) # E꺼           
        ]

        # 메인 부대 대기하는 좌표
        self.hold_points = [
            Point3((52,58,12)), # A꺼
            Point3((36,26,12)), # E꺼
        ]

        
        # 기습공격때 의료선 드랍하는 좌표
        self.surprise_points =[
            Point3((17,32,12)),
            Point3((71,56,12)),
        ]

        self.region_radius = 10
        #my_base 추가
        self.my_base = 0

    def reset(self):
        # 나와 적의 시작위치 설정
        self.start_location = self.bot.start_location
        self.enemy_start_location = self.bot.enemy_start_locations[0]
        self._map_abstraction()

    def step(self):
        # 나와 적의 시작위치 설정
        if self.start_location is None:
            self.reset()

    '''
    def occupied_points(self):
        """
        지점를 점령하고 있는지 여부를 검사
        """
        units = self.bot.units.of_type(ARMY_TYPES).owned
        enemy = self.bot.known_enemy_units

        occupied = list()
        for point in self.strategic_points:
            n_units = units.closer_than(self.region_radius, point).amount
            n_enemy = enemy.closer_than(self.region_radius, point).amount
            # 해당 위치 근처에 내 유닛이 더 많으면 그 지점을 점령하고 있다고 가정함
            #   (내 유닛 개수 - 적 유닛 개수) > 0 이면 점령 중 
            occupied.append(n_units - n_enemy)
                
        return occupied
    '''


    def hold_point(self):
        if self.start_location.position.x<30:
            points = self.hold_points[0]
        else:
            points = self.hold_points[1]
        return points

    def enemy_tank_point(self):
        if self.start_location.position.x<30:
            points = self.enemy_tank_points[0]   
        else:
            points = self.enemy_tank_points[1]
        return points

    
    def surprise_attack(self):
        if self.start_location.position.x<30:
            points = self.surprise_points[0]   
        else:
            points = self.surprise_points[1]
        return points

    def _map_abstraction(self):
        # 내 시작위치를 기준으로 가까운 지역부터 먼 지역까지 정렬함
        if self.start_location.distance2_to(self.strategic_points[0]) < 3:
            points = self.strategic_points
            #occupancy = self.occupied_points()
            self.my_base = 0
        else:
            points = list(reversed(self.strategic_points))
            #occupancy = list(reversed(self.occupied_points()))
            self.my_base = 1
        #return points


class Debuging(object):
    tank_tags = [None, None, None]
    tank_units = [set(), set(), set()]
    tank_pos0 = [Point2((42.66, 53.81)), Point2((31.93, 50.09)), Point2((38.77, 50.36))]
    tank_pos1 = [Point2((46.04, 34.18)), Point2((56.23, 38.07)), Point2((49.15, 38.45))]
    
    vacant_tags = [None, None, None, None, None]
    vacant_units = [set(), set(), set(), set(), set()]
    vacant_pos0 = [Point2((74.44, 56.73)), Point2((74.68, 62.152)), Point2((74.68, 67.28)), Point2((74.68, 71.62)), Point2((71.55, 74.68))]
    vacant_pos1 = [Point2((13.42, 31.98)), Point2((13.31, 27)), Point2((13.31, 21.68)), Point2((13.668,15.789)), Point2((19.59, 13.31))]

    def __init__(self, bot_ai, tactics):
        self.bot = bot_ai
        self.strategy = None
        self.target = None
        self.unit_tags = None
        # 그룹의 경계 범위
        self.perimeter_radious = 10
        self.tactics = tactics
        self.state = ''
        """
        #탱크 포지션
        
        self.tank_tags = [None, None, None]
        self.tank_units = [set(), set(), set()]
        self.tank_pos0 = [Point2((42.66, 53.81)), Point2((31.93, 50.09)), Point2((38.77, 50.36))]
        self.tank_pos1 = [Point2((46.04, 34.18)), Point2((56.23, 38.07)), Point2((49.15, 38.45))]
        
        #공터 방어 포지션
        self.vacant_tags = [None, None, None, None, None]
        self.vacant_units = [set(), set(), set(), set(), set()]
        self.vacant_pos0 = [Point2((74.44, 56.73)), Point2((74.68, 62.152)), Point2((74.68, 67.28)), Point2((74.68, 71.62)), Point2((71.55, 74.68))]
        self.vacant_pos1 = [Point2((13.42, 31.98)), Point2((13.31, 27)), Point2((13.31, 21.68)), Point2((13.668,15.789)), Point2((19.59, 13.31))]
        
        #안티드롭포지션
        self.anti_drop_pos0 = [#의료선, #사신 #해병, #불곰]
        self.anti_drop_pos1 = [#의료선, #사신 #해병, #불곰]
        """
    def reset(self):
        self.unit_tags = (self.bot.units & list()).tags
        #탱크
        for i in range(3):
            Debuging.tank_tags[i] = (self.bot.units & list()).tags

    def get_tank_positions(self):
        if self.start_location.position.x<30:
            points = Debuging.tank_pos0
        else:
            points = Debuging.tank_pos1
        return points

    def units(self):
        return self.bot.units.filter(lambda unit: unit.tag in self.unit_tags)

    async def step(self):
        actions = list()
        units = self.units()

        if units.amount ==0:
            return actions

        enemy = self.bot.known_enemy_units.closer_than(
        self.perimeter_radious, units.center)
        
        for unit in units:
            if self.tactics == Tactics.MAIN:
                actions += await self.main_step(unit, units, enemy)
            if self.tactics == Tactics.MIDDLE:
                actions += await self.middle_step(unit, units)
            if self.tactics == Tactics.VACANT:
                actions += await self.vacant_step(unit, units)
            if self.tactics == Tactics.BASE:
                actions += await self.base_step(unit, units)
            if self.tactics == Tactics.TANK:
                actions += await self.tank_step(unit, units)
            if self.tactics == Tactics.TANK_MOVE:
                actions += await self.tank_move_step(unit, units, enemy)
            if self.tactics == Tactics.ANTI_DROP:
                actions += await self.anti_drop_step(unit, units)
            if self.tactics == Tactics.TANK_DROP:
                actions += await self.tank_drop_step(unit, units)
            if self.tactics == Tactics.PRESS:
                actions += await self.press_step(unit, units)    
            if self.tactics == Tactics.FIRST_VIEW:
                actions += await self.first_view_step(unit, units)

        return actions
                
    async def main_step(self,unit, units, foes):
        """
        아직 의료선 태울 때 누구누구 먼저 태우는지 지정 안하고 마구잡이로 태움
        """
        actions = list()
        if self.bot.strategic_manager.strategy == 'ATTACK':       # 현재 내 전략이 공격일 경우
            self.target = self.bot.terrein_manager.surprise_attack()        #임시로 목표지점 설정해둠
        else:
            self.target = self.bot.terrein_manager.hold_point()

        if self.bot.debug:
            text=[
                f'main'
            ]
            self.bot._client.debug_text_world(''.join(text), unit.position3d, size=16)
        
        if self.bot.step_manager.step > 0:          # 이부분 모르겠다
            medivac = units.of_type(UnitTypeId.MEDIVAC)
            if unit.type_id == UnitTypeId.MARAUDER:
                if foes.amount > 0:
                    if unit.health_percentage > 0.8 and \
                        not unit.has_buff(BuffId.STIMPACK):
                        # 스팀팩 사용
                        order = unit(AbilityId.EFFECT_STIM)
                    else:
                        # 가장 가까운 목표 공격
                        order = unit.attack(foes.closest_to(unit.position))
                    actions.append(order)
                else:
                    if medivac.exists:          #==========이부분 코드 다시 짜야함 내 사령부 집결지 간 다음 메딕에 타기=========
                        if unit.distance_to(medivac.center) > 5:
                            actions.append(unit.move(medivac.center))
                    else:
                        if unit.distance_to(self.target) > 5:
                            actions.append(unit.stop())
                        else:
                            if foes.amount > 0:
                                if unit.health_percentage > 0.8 and not unit.has_buff(BuffId.STIMPACK):
                                    # 스팀팩 사용
                                    order = unit(AbilityId.EFFECT_STIM)
                                else:
                                    # 가장 가까운 목표 공격
                                    order = unit.attack(foes.closest_to(unit.position))
                            actions.append(order)

            elif unit.type_id == UnitTypeId.MEDIVAC:
                is_ready = 0

                if self.bot.debug:
                    text=[
                    f'state : {self.state}\n'
                    f'medics : {units.of_type(UnitTypeId.MEDIVAC).amount}'

                    ]
                self.bot._client.debug_text_world(''.join(text), unit.position3d, size=16)
                
                for m in medivac:               # 모든 의료선이 탑승인원 꽉 채웠는지 점검
                    if m.cargo_used == m.cargo_max:
                        is_ready +=1

                if is_ready == len(medivac):
                    self.state = 'go'
                else :
                    self.state = 'ready'

                if self.state == 'ready':
                    if unit.cargo_used < unit.cargo_max:    # 탑승인원의 최대치보다 적으면
                        assult_units = units.of_type((UnitTypeId.MARINE, UnitTypeId.MARAUDER, UnitTypeId.SIEGETANK, UnitTypeId.SIEGETANKSIEGED))
                        if assult_units.amount > 0:
                            if self.bot.debug:
                                text=[
                                f'assult_unit \n'
                                ]                            
                            self.bot._client.debug_text_world(''.join(text), assult_units.first.position3d, size=16)
                            order = unit(AbilityId.LOAD, assult_units.first)
                            actions.append(order)

                elif self.state == 'go':
                    if unit.distance_to(self.target) < 13:
                        actions.append(unit(AbilityId.EFFECT_MEDIVACIGNITEAFTERBURNERS))
                    
                    if unit.distance_to(self.target) > 5:    #적 공터으로 처들어감 # 적 공터 좌표 얼른 알려줘!
                        actions.append(unit.move(self.target))    
                    else:
                        actions.append(unit.stop())
                        self.state = 'combat'

                elif self.state == 'combat':
                    if len(unit.passengers) > 0:
                        order = unit(AbilityId.UNLOADALLAT, unit.position)
                        actions.append(order)

                    if foes.amount > 20 :
                        self.state = 'fallback'


                elif self.state == 'fallback':
                    assult_units = self.bot.units.filter(lambda u: u.tag in self.unit_tags).of_type(ARMY_TYPES)
                    assult_units = assult_units.filter(lambda u: u.distance_to(unit.position) < 10)
                    if len(assult_units) > 0:
                        order = unit(AbilityId.LOAD, assult_units.first)
                        actions.append(order)
                    else:
                        if unit.distance_to(self.target) > 5:
                            actions.append(unit.move(self.target))
                        else:
                            self.state = 'ready'

                else:
                    self.state = 'ready'

            if unit.type_id == UnitTypeId.MARINE:   #마린에게 내리는 명령============여기도 서프라이즈 모드로 다시 짜야함==========
                if foes.amount > 0:
                    if unit.health_percentage > 0.8 and \
                        not unit.has_buff(BuffId.STIMPACK):
                        # 스팀팩 사용
                        order = unit(AbilityId.EFFECT_STIM)
                    else:
                        # 가장 가까운 목표 공격
                        order = unit.attack(foes.closest_to(unit.position))
                    actions.append(order)
                else:
                    if medivac.exists:          #==========이부분 코드 다시 짜야함 내 사령부 집결지 간 다음 메딕에 타기=========
                        
                        if unit.distance_to(medivac.center) > 5:
                            actions.append(unit.move(medivac.center))
                    else:
                        if unit.distance_to(self.target) > 5:
                            actions.append(unit.stop())
                        else:
                            if foes.amount > 0:
                                if unit.health_percentage > 0.8 and not unit.has_buff(BuffId.STIMPACK):
                                    # 스팀팩 사용
                                    order = unit(AbilityId.EFFECT_STIM)
                                else:
                                    # 가장 가까운 목표 공격
                                    order = unit.attack(foes.closest_to(unit.position))
                            actions.append(order)

            elif unit.type_id == UnitTypeId.REAPER:     #리퍼한테 내리는 명령
                threaten = self.bot.known_enemy_units.closer_than(  #나에 대한 위협부터 감지해본다
                        self.perimeter_radious, unit.position)
                if(foes.amount>0):  #적이 있으면
                    if unit.health_percentage > 0.3 and unit.energy >= 50:
                        if threaten.amount > 0:
                            if unit.orders and unit.orders[0].ability.id != AbilityId.BUILDAUTOTURRET_AUTOTURRET:   #포탑짓기
                                closest_threat = threaten.closest_to(unit.position)
                                pos = unit.position.towards(closest_threat.position, 5)
                                pos = await self.bot.find_placement(UnitTypeId.AUTOTURRET, pos)
                                order = unit(AbilityId.BUILDAUTOTURRET_AUTOTURRET, pos)
                                actions.append(order)
                        else:
                            if unit.distance_to(medivac.center) > 5:   #그냥 집결 장소에 대기하기
                                order = unit.move(medivac.center)
                                actions.append(order)

        return actions


    async def middle_step(self,unit, units):    # 중앙 지키는 부대

        enemy = self.bot.known_enemy_units.closer_than(6, units.of_type(UnitTypeId.MEDIVAC).first.position)
        enemy = enemy.of_type([UnitTypeId.MARINE , UnitTypeId.AUTOTURRET])
        enemy_medivac = self.bot.known_enemy_units.closer_than(5, Point2((45, 45)))
        enemy_medivac = enemy_medivac.of_type(UnitTypeId.MEDIVAC)
        actions = list()

        medic_is_in = 0
        medic_alert = 0
        turret_is_in = 0

        #자동 포탑이 안에 있냐
        turrets = self.bot.units.of_type(UnitTypeId.AUTOTURRET).owned.closer_than(5, Point2((45, 45)))
        if turrets.amount > 0:
            turret_is_in = 1
        else:
            turret_is_in = 0

        #의료선
        if unit.type_id == UnitTypeId.MEDIVAC:
            
            #의료선 안에 있냐
            if unit.distance_to(Point2((45, 45))) < 5:
                medic_is_in = 1
            else:
                medic_is_in = 0

            #적 있음
            if enemy.amount > 0:
                pos = unit.position.towards(self.bot.units.of_type(UnitTypeId.COMMANDCENTER).owned,2)
                order = unit.move(pos)
                actions.append(order)
            #적 없음
            else:
                if unit.distance_to(Point2((45, 45)))>5:
                    if self.bot.terrein_manager.my_base == 0: #거점 0
                        order = unit.move(Point2((39.33, 48.44)))
                    else:  #거점 1
                        order = unit.move(Point2((46.84, 39.238)))
        #리퍼
        if unit.type_id == UnitTypeId.REAPER:
            if enemy.amount > 0 | medic_is_in == 0 | enemy_medivac.amount > 0:
                if unit.health_percentage > 0.2 and unit.energy >= 5 and turrets.amount < 3:
                    closest_threat = enemy.closest_to(unit.position)
                    if closest_threat.amount >0:
                        pos = unit.position.towards(closest_threat.position, 5)
                        pos = await self.bot.find_placement(UnitTypeId.AUTOTURRET, pos)

                        order = unit(AbilityId.BUILDAUTOTURRET_AUTOTURRET, pos)
                        actions.append(order)
                else:
                    if self.bot.terrein_manager.my_base == 0:
                        pos = unit.position.towards(self.bot.units.of_type(UnitTypeId.COMMANDCENTER).owned.position,5)

                        order = unit.move(pos)
                        actions.append(order)
                        
                    elif self.bot.terrein_manager.my_base == 1:
                        pos = unit.position.towards(self.bot.units.of_type(UnitTypeId.COMMANDCENTER).owned.position, 5)

                        order = unit.move(pos)
                        actions.append(order)

        

        #마린, 사신/포탑이 사정거리 안에 있으면 fallback, 이때 미들 사신이 안에다 포탑을 던져놓는다.

        if self.bot.debug:
            text=[
                    f'x : middle_view\n'
                ]
            self.bot._client.debug_text_world(''.join(text), unit.position3d, size=16)

        
        return actions

    async def vacant_step(self,unit, units):
        actions = list()

        alert = 0
        #감지하는 의료선의 개수대로 메인 부대의 의료선 부름 적의 위치로 보냄

        for i in range(5):
            Debuging.vacant_units[i] = self.get_one_marine(units, i)

        vacant_units = Debuging.vacant_units

        if self.bot.terrein_manager.my_base == 0:
            for i in range(5):
                if vacant_units[i].amount > 0:
                    if vacant_units[i].first.distance_to(Debuging.vacant_pos0[i])<1:
                        order = vacant_units[i].move(Debuging.vacant_pos0[i])
                        actions.append(order)
                    else:
                        pass
        else:
            for i in range(5):
                if vacant_units[i].amount > 0:
                    if vacant_units[i].first.distance_to(Debuging.vacant_pos1[i])<1:
                        order = vacant_units[i].move(Debuging.vacant_pos1[i])
                        actions.append(order)
                    else:
                        pass

        return actions

    async def base_step(self,unit, units):
        actions = list()
        
        alert = 0

        if self.bot.terrein_manager.my_base == 0:
            if unit.distance_to(Point2((21.99, 45.37)))<1:
                order = unit.move(Point2((21.99, 45.37)))
                actions.append(order)
            #사람들 감지했을때 : 5명당 1대씩 의료선 부르기 
                #후에 압박을 하게 될 경우 압박부대로 편성됨
        else:
            if unit.distance_to(Point2((65.54, 26.29)))<1:
                order = unit.move(Point2((65.54, 26.29)))
                actions.append(order)

        return actions

    async def tank_step(self,unit, units):
        actions = list()

        for i in range(3):
            Debuging.tank_units[i] = self.get_one_tank(units, i)

        tank_units = Debuging.tank_units

        if self.bot.terrein_manager.my_base == 0:
            for i in range(3):
                if tank_units[i].amount > 0:
                    if tank_units[i].first.type_id == UnitTypeId.SIEGETANK:
                        if tank_units[i].first.distance_to(Debuging.tank_pos0[i])<1:
                            order = tank_units[i].first(AbilityId.SIEGEMODE_SIEGEMODE)
                            actions.append(order)
                    else:
                        order = tank_units[i].first.move(Debuging.tank_pos0[i])
                        actions.append(order)
        else:
            for i in range(3):
                if tank_units[i].amount > 0:
                    if tank_units[i].first.type_id == UnitTypeId.SIEGETANK:
                        if tank_units[i].first.distance_to(Debuging.tank_pos1[i])<1:
                            order = tank_units[i].first(AbilityId.SIEGEMODE_SIEGEMODE)
                            actions.append(order)
                    else:
                        order = tank_units[i].first.move(Debuging.tank_pos1[i])
                        actions.append(order)
           

        for i in range(3):
            one_unit =  self.bot.units.filter(lambda u : u.tag in Debuging.tank_tags[i])
            for one in one_unit:
                if self.bot.debug:
                    text=[
                        f'tank# : {i}\n'
                        f'unit amount : {one_unit.amount}\n'
                        ]
                    self.bot._client.debug_text_world(''.join(text), one.position3d, size=16)
                
        return actions

    def get_one_tank(self, units, number):
        self.number = number
        tags_in_tank_tags = set()

        if Debuging.tank_tags[number] == None:
            group_units_tags = set()
        else:
            group_units_tags = units.tags & Debuging.tank_tags[number]
            for i in range(3):
                tags_in_tank_tags = tags_in_tank_tags | Debuging.tank_tags[i]
        group_units = self.bot.units.filter(lambda u: u.tag in group_units_tags)
                
        #group_units_tags = units.tags & Debuging.vacant_tags[number]
        #group_units = units.filter(lambda u: u.tag in group_units_tags)
        #for i in range(5):
        #    tags_in_vacant_tags = tags_in_vacant_tags | Debuging.vacant_tags[i]
        


            
        new_units = self.bot.units & list()

        has_left = False

        left_index = 0

        for i in range(2-number):
            if len(Debuging.tank_units[number+1]) > 0 :
                has_left = True
                left_index = number+1
                break
        
        if has_left == True and (group_units.of_type(UnitTypeId.MARINE)).amount == 0:
            new_units = Debuging.tank_units[left_index]
            new_units_for_left = self.bot.units & list()
            new_units_for_left = new_units_for_left | units.tags_not_in(tags_in_tank_tags).take(1)
            Debuging.tank_tags[left_index] = (new_units_for_left).tags

        if has_left == False:
            if (group_units.of_type(UnitTypeId.MARINE)).amount == 0 and units.amount>=1:
                new_units = new_units | units.tags_not_in(tags_in_tank_tags).take(1)

        unit_tags = (group_units | new_units).tags

        Debuging.tank_tags[number] = unit_tags

        return group_units | new_units

    def get_one_marine(self, units, number):
        self.number = number
        tags_in_vacant_tags = set()

        if Debuging.vacant_tags[number] == None:
            group_units_tags = set()
        else:
            group_units_tags = units.tags & Debuging.vacant_tags[number]
            for i in range(5):
                tags_in_vacant_tags = tags_in_vacant_tags | Debuging.vacant_tags[i]
        group_units = self.bot.units.filter(lambda u: u.tag in group_units_tags)
                
        #group_units_tags = units.tags & Debuging.vacant_tags[number]
        #group_units = units.filter(lambda u: u.tag in group_units_tags)
        #for i in range(5):
        #    tags_in_vacant_tags = tags_in_vacant_tags | Debuging.vacant_tags[i]
        


            
        new_units = self.bot.units & list()

        has_left = False

        left_index = 0

        for i in range(4-number):
            if len(Debuging.vacant_units[number+1]) > 0 :
                has_left = True
                left_index = number+1
                break
        
        if has_left == True and (group_units.of_type(UnitTypeId.MARINE)).amount == 0:
            new_units = Debuging.vacant_units[left_index]
            new_units_for_left = self.bot.units & list()
            new_units_for_left = new_units_for_left | units.tags_not_in(tags_in_vacant_tags).take(1)
            Debuging.vacant_tags[left_index] = (new_units_for_left).tags

        if has_left == False:
            if (group_units.of_type(UnitTypeId.MARINE)).amount == 0 and units.amount>=1:
                new_units = new_units | units.tags_not_in(tags_in_vacant_tags).take(1)

        unit_tags = (group_units | new_units).tags

        Debuging.vacant_tags[number] = unit_tags

        return group_units | new_units

    async def tank_move_step(self, unit, units, foes):
        actions = list()
        if unit.type_id == UnitTypeId.MEDIVAC:
            if self.bot.debug:
                text=[
                f'state : {self.state}\n'
                ]
            self.bot._client.debug_text_world(''.join(text), unit.position3d, size=16)

            if self.state == 'ready':
                if len(unit.passengers.of_type(UnitTypeId.SIEGETANKSIEGED, UnitTypeId.SIEGETANK)) <0:    
                    if self.bot.debug:
                        text=[
                        f'assult_unit \n'
                        ]
                    self.bot.main_manager.unit_tags += self.unit_tags
                    self.unit_tags = None                            
                else : #두마리 딱 태웠으면 떠나자
                    self.state = 'go'

            elif self.state == 'go':
                if unit.distance_to(Debuging.get_tank_positions()) > 2:    # 적 탱크 좌표로 쳐들어감
                    actions.append(unit.move(Debuging.get_tank_positions()))    
                else:
                    actions.append(unit.stop())
                    self.state = 'combat'
            elif self.state == 'combat':
                if len(unit.passengers) > 0:
                    order = unit(AbilityId.UNLOADUNIT, unit.passengers.of_type((UnitTypeId.SIEGETANK, UnitTypeId.SIEGETANKSIEGED)).first)
                    actions.append(order)                    
                    self.bot.main_manager.unit_tags += self.unit_tags
                    self.unit_tags = None
                    
                if len(unit.passengers) ==0 :
                    self.bot.main_manager.unit_tags += self.unit_tags
                    self.unit_tags = None
            else:
                self.state = 'ready'


        return actions

    async def anti_drop_step(self,unit, units):
        actions = list()

        #적을 어떻게 판단할 것인지?
        enemy = self.bot.known_enemy_units.closer_than(self.perimeter_radious, units.center)
        enemy = enemy | self.bot.known_enemy_units.closer_than(self.perimeter_radious, unit)

        if self.bot.debug:
            text=[
                f'antidrop'
            ]
            self.bot._client.debug_text_world(''.join(text), unit.position3d, size=16)
        
        #경고
        alert = 0

        if enemy.amount ==0:
            if self.bot.terrein_manager.my_base == 0:
                if unit.type_id == UnitTypeId.MARINE:
                    if self.bot.debug:
                            text=[f'marine']
                            self.bot._client.debug_text_world(''.join(text), unit.position3d, size=16)

                    if unit.distance_to(Point2((68.6, 54.64))) > 4 :
                        order = unit.move(Point2((68.6, 54.64)))
                        actions.append(order)

                        if self.bot.debug:
                            text=[
                                f'need to move'
                                ]
                            self.bot._client.debug_text_world(''.join(text), unit.position3d, size=16)
            
                elif unit.type_id == UnitTypeId.REAPER:
                    if unit.distance_to(Point2((68.6, 54.64))) > 5:
                        order = unit.move(Point2((68.6, 54.64)))
                        actions.append(order)

                elif unit.type_id == UnitTypeId.MEDIVAC:
                    if unit.distance_to(Point2((65.98, 50.88))) > 2:
                        order = unit.move(Point2((65.98, 50.88)))
                        actions.append(order)
                elif unit.type_id == UnitTypeId.MARAUDER:
                    if unit.distance_to(Point2((65.98, 50.88))) > 2:
                        order = unit.move(Point2((65.98, 50.88)))
                        actions.append(order)

            elif self.bot.terrein_manager.my_base == 1:
            
                if unit.type_id == UnitTypeId.MARINE:
                
                    if self.bot.debug:
                            text=[
                                f'marine'
                                ]
                            self.bot._client.debug_text_world(''.join(text), unit.position3d, size=16)
                
                    if unit.distance_to(Point2((19, 31.7))) > 1:
                        if self.bot.debug:
                            text=[
                                f'need to move'
                                ]
                            self.bot._client.debug_text_world(''.join(text), unit.position3d, size=16)
                        
                        order = unit.move(Point2((19,31.7)))
                        actions.append(order)
            
                elif unit.type_id == UnitTypeId.REAPER:
                    if unit.distance_to(Point2((19,31.7))) > 5:
                        order = unit.move(Point2((19,31.7)))
                        actions.append(order)

                elif unit.type_id == UnitTypeId.MEDIVAC:
                    if unit.distance_to(Point2((21.14, 34.9))) > 2:
                        order = unit.move(Point2((21.14, 34.9)))
                        actions.append(order)

            
        if enemy.amount > 0:
            
            alert = enemy.of_type(UnitTypeId.MEDIVAC).amount
            
            if unit.type_id == UnitTypeId.MARINE:
                #타겟팅을 어떻게 하지,,,?
                order = unit.attack(enemy.closest_to(unit.position))
                actions.append(order)

            elif unit.type_id == UnitTypeId.REAPER:

                if unit.health_percentage > 0.2 and unit.energy > 5:
                    closest_threat = enemy.closest_to(unit.position)
                    pos = unit.position.towards(closest_threat.position, 5)
                    pos = await self.bot.find_placement(UnitTypeId.AUTOTURRET, pos)

                    order = unit(AbilityId.BUILDAUTOTURRET_AUTOTURRET, pos)
                    actions.append(order)

                elif unit.health_percentage <= 0.2 or unit.energy < 5:
                    
                    if self.bot.terrein_manager.my_base == 0:
                        pos = unit.position.towards(Point2((58.5, 63.5)),5)

                        order = unit.move(pos)
                        actions.append(order)
                        
                    elif self.bot.terrein_manager.my_base == 1:
                        pos = unit.position.towards(Point2((58.5, 63.5)), 5)

                        order = unit.move(pos)
                        actions.append(order)
                    
                    


            elif unit.type_id == UnitTypeId.MEDIVAC:
                    if self.bot.terrein_manager.my_base == 0:
                        pos = unit.position.towards(Point2((58.5, 63.5)),2)

                        order = unit.move(pos)
                        actions.append(order)
                        
                    elif self.bot.terrein_manager.my_base == 1:
                        
                        pos = unit.position.towards(Point2((58.5, 63.5)), 2)

                        order = unit.move(pos)
                        actions.append(order)
        
        return actions

    async def tank_drop_step(self,unit, units):
        actions = list()        
        if self.bot.step_manager.step>60:    
            if unit.type_id == UnitTypeId.MEDIVAC:
                if self.bot.debug:
                    text=[
                    f'state : {self.state}\n'
                    ]
                self.bot._client.debug_text_world(''.join(text), unit.position3d, size=16)

                if self.state == 'ready':
                    if len(unit.passengers) <2:    # 불곰 2마리를 아직 안태웠으면
                        friends_units =  self.bot.units.filter(lambda u: u.tag in self.unit_tags).of_type((UnitTypeId.MARAUDER))         
                        if friends_units.amount >0:
                            #지정할 경우, assult_units = friends
                            if self.bot.debug:
                                text=[
                                f'assult_unit \n'
                                ]                            
                            #self.bot._client.debug_text_world(''.join(text), assult_units.first.position3d, size=16)
                            order = unit(AbilityId.LOAD, friends_units.first)
                            actions.append(order)
                    else : #두마리 딱 태웠으면 떠나자
                            self.state = 'go'

                elif self.state == 'go':
                    if unit.distance_to(self.target) < 10:      # 부스터 켜기
                        actions.append(unit(AbilityId.EFFECT_MEDIVACIGNITEAFTERBURNERS))
                    if unit.distance_to(self.target) > 5:    # 적 탱크 좌표로 쳐들어감
                        actions.append(unit.move(self.target))    
                    else:
                        actions.append(unit.stop())
                        self.state = 'combat'

                elif self.state == 'combat':
                    if len(unit.passengers) > 0:
                        order = unit(AbilityId.UNLOADALLAT, unit.position)
                        actions.append(order)

                    if len(unit.passengers) ==0 :
                        self.state = 'fallback'


                elif self.state == 'fallback':
                    if unit.distance_to(self.bot.start_location) > 5:
                        actions.append(unit.move(self.bot.start_location))
                    else:
                        self.state = 'ready'

                else:
                    self.state = 'ready'

        return actions

    async def press_step(self,unit, units):
        """
        의료선, 탱크는 했음 점검은 안함
        사신 안함
        """

        actions = list()

        #state가 공격이 되면 1. 의료선이 탱크를 태우고 정찰, 2. 사신이 포탑 세우고 튀면 3. 그 뒤에 탱크 드랍 4.전진반복
        if self.bot.strategic_manager.strategy == 'ATTACK':
            if unit.type_id == UnitTypeId.SIEGETANK or unit.type_id == UnitTypeId.SIEGETANKSIEGED:
                if self.state == ('go' or 'ready' or 'fallback'):
                    order = unit(AbilityId.UNSIEGE_UNSIEGE) # 시즈 모드 해제
                    actions.append(order)
                elif self.state == 'combat' :
                    order = unit(AbilityId.SIEGEMODE_SIEGEMODE)
                    actions.append(order)
                else:
                    self.state = 'ready'

            if unit.type_id == UnitTypeId.MEDIVAC:
                if self.bot.debug:
                    text=[
                    f'state : {self.state}\n'
                    ]
                self.bot._client.debug_text_world(''.join(text), unit.position3d, size=16)

                if self.state == 'ready':
                    if len(unit.passengers) <4:    # 탑승인원의 최대치보다 적으면
                        if self.bot.debug:
                            text=[
                            f'assult_unit \n'
                            ]                            
                        self.bot._client.debug_text_world(''.join(text), assult_units.first.position3d, size=16)
                        order = unit(AbilityId.LOAD, tank)
                        actions.append(order)
                        if unit.cargo_used == 4:
                            self.state = 'go'

                elif self.state == 'go':
                    if unit.distance_to(self.target) > 5:    #적 공터으로 처들어감 # 적 공터 좌표 얼른 알려줘!
                        actions.append(unit.move(self.target))
                        if foes.amount > 0 and  distance_to(foes.closest_to(unit.point).point)<10:
                            actions.append(unit.stop())
                            self.state = 'combat'

                    else:
                        actions.append(unit.stop())
                        self.state = 'combat'

                elif self.state == 'combat':    
                    if len(unit.passengers) > 0:
                        order = unit(AbilityId.UNLOADALLAT, unit.position)
                        actions.append(order)
                    else:               # 적이 주변에 없으면 다시 target point로 go
                        order = unit(AbilityId.LOAD, tank)
                        actions.append(order)
                        self.state = 'go'

                    if foes.amount > 20 :
                        self.state = 'fallback'

                elif self.state == 'fallback':
                    assult_units = self.bot.units.filter(lambda u: u.tag in self.unit_tags).of_type((UnitTypeId.TANK,UnitTypeId.SIEGETANKSIEGED))
                    assult_units = assult_units.filter(lambda u: u.distance_to(unit.position) < 10)
                    if len(assult_units) > 0 and unit.cargo_used <8:
                        order = unit(AbilityId.LOAD, assult_units.first)
                        actions.append(order)
                    else:
                        if unit.distance_to(self.bot.terrein_manager.hold_point()) > 5:
                            actions.append(unit.move(self.bot.terrein_manager.hold_point()))
                        else:
                            self.state = 'ready'

                else:
                    self.state = 'ready'

            
        elif self.bot.strategic_manager.strategy == 'HOLD':  # 다시 원래 부대로 되돌려보내기
            if unit.type_id == (UnitTypeId.SIEGETANKSIEGED or UnitTypeId.SIEGETANK):
                order = unit(AbilityId.UNSIEGE_UNSIEGE) # 시즈 모드 해제
                actions.append(order)
                self.bot.tank_manager.unit_tags += unit.tag
                self.unit_tags = None

            if unit.type_id == UnitTypeId.MEDIVAC:    
                    if unit.cargo_used <4:
                        order = unit(AbilityId.LOAD, assult_units.first)
                        actions.append(order)
                    else:
                        if unit.distance_to(get_tank_positions()[1]) > 5:       # 탱크 원래 자리로 돌려놓기
                            actions.append(unit.move(get_tank_positions()[1]))
                        else:
                            order = unit(AbilityId.UNLOADALLAT, unit.position)
                            actions.append(order)
                            self.bot.base_manager.unit_tags += unit.tag

        return actions
    
    async def first_view_step(self, unit, units):
        actions = list()
        enemy = self.bot.known_enemy_units.closer_than(self.perimeter_radious, units.center)
        enemy = enemy | self.bot.known_enemy_units.closer_than(self.perimeter_radious, unit)

        if self.bot.debug:
                    text=[
                        f'first_view'
                        ]
                    self.bot._client.debug_text_world(''.join(text), unit.position3d, size=16)
                    
        if self.bot.step_manager.step < 30:
            
            if unit.type_id == UnitTypeId.MARINE:
                #여기서 내 거점 별 그거로 나눠야 할 듯
                if self.bot.terrein_manager.my_base == 0:
                    order = unit.move(Point2((34.9, 51.6)))
                    actions.append(order)
                elif self.bot.terrein_manager.my_base == 1:
                    order = unit.move(Point2((52.6, 36.18)))
                    actions.append(order)

                if self.bot.debug:
                    text=[
                        f'first_view_step'
                        ]
                    self.bot._client.debug_text_world(''.join(text), unit.position3d, size=16)
                    

        else:
            self.main_step(unit, units, enemy)
            if self.bot.debug:
                    text=[
                        f'first_view_step_end'
                        ]
                    self.bot._client.debug_text_world(''.join(text), unit.position3d, size=16)
                    
             

        return actions

    
    def debug(self):
        pass

            
class Tactics(Enum):
    MAIN = 0
    MIDDLE = 1
    VACANT = 2
    BASE = 3
    TANK = 4
    TANK_MOVE = 5
    ANTI_DROP = 6
    TANK_DROP = 7
    PRESS = 8
    FIRST_VIEW = 9
    
class AssignManager(object):
    """
    유닛을 부대에 배치하는 매니저
    """
    def __init__(self, bot_ai, *args, **kwargs):
        self.bot = bot_ai
        self.normal_unit=None
        self.tank_unit=None
        self.bunker_loaded = False
        

    def reset(self):
        pass

    def assign(self, manager):

        units = self.bot.units

        if manager.tactics is Tactics.MAIN:
            #메인부대
            units = self.bot.units.of_type(ARMY_TYPES).owned
            unit_tags = units.tags
            #unit_tags = unit_tags - self.bot.medic_manager.unit_tags
    
            self.tank_unit = len(unit_tags)

            unit_tags = unit_tags - self.bot.middle_manager.unit_tags
            unit_tags = unit_tags - self.bot.vacant_manager.unit_tags
            unit_tags = unit_tags - self.bot.base_manager.unit_tags
            unit_tags = unit_tags - self.bot.tank_manager.unit_tags
            unit_tags = unit_tags - self.bot.tank_move_manager.unit_tags
            unit_tags = unit_tags - self.bot.anti_drop_manager.unit_tags
            unit_tags = unit_tags - self.bot.tank_drop_manager.unit_tags
            unit_tags = unit_tags - self.bot.press_manager.unit_tags
            unit_tags = unit_tags - self.bot.first_view_manager.unit_tags
            
            manager.unit_tags = unit_tags

        elif manager.tactics is Tactics.MIDDLE:
           # 현재 지도에 존재하는 그룹 유닛
            group_units_tags = self.bot.units.tags & manager.unit_tags
            group_units = self.bot.units.filter(lambda u: u.tag in group_units_tags)
            
            # 새 유닛 요청            
            new_units = self.bot.units & list()

            medivacs = self.bot.units(UnitTypeId.MEDIVAC).owned 
            if (group_units.of_type(UnitTypeId.MEDIVAC).amount) == 0 and medivacs.amount > 0:
                new_units = new_units | medivacs.take(1)

            reapers = self.bot.units(UnitTypeId.REAPER).owned 
            if group_units.of_type(UnitTypeId.REAPER).amount < 2 and reapers.amount > 0:
                new_units = new_units | reapers.take(1)

            unit_tags = (group_units | new_units).tags
            
            # 다른 매니저가 사용 중인 유닛 제외
            # unit_tags = unit_tags - self.bot.combat_manager.unit_tags
            manager.unit_tags = unit_tags
            
        elif manager.tactics is Tactics.VACANT:
           # 현재 지도에 존재하는 그룹 유닛
            group_units_tags = self.bot.units.tags & manager.unit_tags
            group_units = self.bot.units.filter(lambda u: u.tag in group_units_tags)
            
            # 새 유닛 요청            
            new_units = self.bot.units & list()

            marines = self.bot.units(UnitTypeId.MARINE).owned
            if group_units.of_type(UnitTypeId.MARINE).amount < 5 and marines.amount > 0:
                new_units = new_units | marines.take(1)

            unit_tags = (group_units | new_units).tags
            
            # 다른 매니저가 사용 중인 유닛 제외
            # unit_tags = unit_tags - self.bot.combat_manager.unit_tags
            unit_tags = unit_tags - self.bot.anti_drop_manager.unit_tags
            manager.unit_tags = unit_tags

        elif manager.tactics is Tactics.BASE:
            if self.bot.strategic_manager.strategy is not 'ATTACK':
            # 현재 지도에 존재하는 그룹 유닛
                group_units_tags = self.bot.units.tags & manager.unit_tags
                group_units = self.bot.units.filter(lambda u: u.tag in group_units_tags)
                
                # 새 유닛 요청            
                new_units = self.bot.units & list()

                medivacs = self.bot.units(UnitTypeId.MEDIVAC).owned
                if group_units.of_type(UnitTypeId.MEDIVAC).amount == 0 and medivacs.amount > 0:
                    new_units = new_units | medivacs.take(1)

                unit_tags = (group_units | new_units).tags
                
                # 다른 매니저가 사용 중인 유닛 제외
                # unit_tags = unit_tags - self.bot.combat_manager.unit_tags
                #unit_tags = unit_tags - self.bot.normal_manager.unit_tags
                #unit_tags = unit_tags - self.bot.medic_manager.unit_tags
                manager.unit_tags = unit_tags
            
        elif manager.tactics is Tactics.TANK:
           # 현재 지도에 존재하는 그룹 유닛
            group_units_tags = self.bot.units.tags & manager.unit_tags
            group_units = self.bot.units.filter(lambda u: u.tag in group_units_tags)
            
            # 새 유닛 요청            
            new_units = self.bot.units & list()

            tanks = self.bot.units(UnitTypeId.SIEGETANK).owned
            if group_units.of_type([UnitTypeId.SIEGETANKSIEGED, UnitTypeId.SIEGETANK]).amount < 3 and tanks.amount > 0:
                new_units = new_units | tanks.take(1)
            marines = self.bot.units(UnitTypeId.MARINE).owned
            '''
            group_tanks_num = group_units.of_type([UnitTypeId.SIEGETANKSIEGED, UnitTypeId.SIEGETANK]).amount
            if group_units.of_type(UnitTypeId.MARINE).amount < group_tanks_num*3  and marines.amount > 0: ##########논의필요
                new_units = new_units | marines.take(1)
            '''
                    
            unit_tags = (group_units | new_units).tags
            
            # 다른 매니저가 사용 중인 유닛 제외
            # unit_tags = unit_tags - self.bot.combat_manager.unit_tags
            manager.unit_tags = unit_tags

        elif manager.tactics is Tactics.TANK_MOVE:
            if Debuging.tank_tags[2] == None:
            # 현재 지도에 존재하는 그룹 유닛
                group_units_tags = self.bot.units.tags & manager.unit_tags
                group_units = self.bot.units.filter(lambda u: u.tag in group_units_tags)
                
                new_units = self.bot.units & list()

                for medivac in self.bot.main_manager.units.of_type(UnitTypeId.MEDIVAC):
                    for tank in medivac.passengers:
                        if tank.type_id == (SIEGETANK or SIEGETANKSIEGED) and group_units.of_type(UnitTypeId.MEDIVAC).amount < 1 and group_units.of_type((UnitTypeId.SIEGETANK,UnitTypeId.SIEGETANKSIEGED)).amount < 1:
                            new_units = new_units | medivac.take(1)
                            self.bot.main_manager.unit_tags -= tank.tag        # 내 태그 다른 부대에서 빼기
                            self.bot.tank_manager.unit_tags += tank.tag
                            Debuging.tank_tags[2] = tank.tag
                            Debuging.tank_units[2] = tank
                unit_tags = (group_units | new_units).tags
                manager.unit_tags = unit_tags
                self.bot.main_manager.unit_tags -= manager.unit_tags        # 내 태그 다른 부대에서 빼기
                self.bot.main_manager.unit_tags -= manager.unit_tags        # 내 태그 다른 부대에서 빼기

            
                        


           
        elif manager.tactics is Tactics.ANTI_DROP:
           # 현재 지도에 존재하는 그룹 유닛
            group_units_tags = self.bot.units.tags & manager.unit_tags
            group_units = self.bot.units.filter(lambda u: u.tag in group_units_tags)
            
            # 새 유닛 요청            
            new_units = self.bot.units & list()

            marines = self.bot.units(UnitTypeId.MARINE).owned 
            if group_units.of_type(UnitTypeId.MARINE).amount < 3 and marines.amount > 0:
                new_units = new_units | marines.take(1)
            medivacs = self.bot.units(UnitTypeId.MEDIVAC).owned 
            if group_units.of_type(UnitTypeId.MEDIVAC).amount == 0 and medivacs.amount > 0:
                new_units = new_units | medivacs.take(1)
            marauders = self.bot.units(UnitTypeId.MARAUDER).owned 
            if group_units.of_type(UnitTypeId.MARAUDER).amount < 1 and marauders.amount > 0: 
                new_units = new_units | marauders.take(1)
            reapers = self.bot.units(UnitTypeId.REAPER).owned 
            if group_units.of_type(UnitTypeId.REAPER).amount < 2 and reapers.amount > 0:
                new_units = new_units | reapers.take(1)
                    
            unit_tags = (group_units | new_units).tags
            
            # 다른 매니저가 사용 중인 유닛 제외
            # unit_tags = unit_tags - self.bot.combat_manager.unit_tags
            manager.unit_tags = unit_tags
            
        elif manager.tactics is Tactics.TANK_DROP:
            if self.bot.isTankDropTiming and tank_drop_init == False:   #지금이 tankdrop 할 타이밍인지 체크
                if manager.unit_tags == None:
                    group_units_tags = set()
                else:
                    group_units_tags = manager.unit_tags
                group_units = self.bot.units.filter(lambda u: u.tag in group_units_tags)
                
                # 새 유닛 요청            
                new_units = self.bot.units & list()

                medivacs = self.bot.middle_manager.units(UnitTypeId.MEDIVAC).owned
                #주의!!! 여기서 가운데 시야 지키는 메딕은 빠져야함 (<- 뭔소리야???? 2020-01-03)
                if group_units.of_type(UnitTypeId.MEDIVAC).amount == 0 and medivacs.amount > 1:
                    new_units = new_units | medivacs.tags_not_in(group_units.tags).take(1)

                marauders = self.bot.units(UnitTypeId.MARAUDER).owned
                if group_units.of_type(UnitTypeId.MARAUDER).amount < 2 and marauders.amount > 0:
                    new_units = new_units | marauders.tags_not_in(group_units.tags).take(1)

                unit_tags = (group_units | new_units).tags
                
                # 다른 매니저가 사용 중인 유닛 제외
                # unit_tags = unit_tags - self.bot.combat_manager.unit_tags
                #unit_tags = unit_tags - self.middle_main_manager.unit_tags
                manager.unit_tags = unit_tags
                tank_drop_init = True
            else :
                manager.unit_tags = set()

        elif manager.tactics is Tactics.PRESS:
            global press_init

            if self.bot.strategic_manager.strategy == 'ATTACK' and press_init == False :
                # 현재 지도에 존재하는 그룹 유닛
                group_units_tags = self.bot.units.tags & manager.unit_tags
                group_units = self.bot.units.filter(lambda u: u.tag in group_units_tags)
                
                # 새 유닛 요청            
                new_units = self.bot.units & list()

                medivacs = self.bot.units.tags & self.bot.base_manager.unit_tags 
                if group_units.of_type(UnitTypeId.MEDIVAC).amount == 0 and medivacs.amount > 0:
                    new_units = new_units | medivacs.take(1)

                tank = self.bot.units.tags & Debuging.tank_tags[1]
                if group_units.of_type(UnitTypeId.MEDIVAC).amount == 0 and tank.amount > 0:
                    new_units = new_units | tank.take(1)    

                reapers = self.bot.units(UnitTypeId.REAPER).owned 
                if group_units.of_type(UnitTypeId.REAPER).amount < 2 and reapers.amount > 0:
                    new_units = new_units | reapers.take(1)

                unit_tags = (group_units | new_units).tags
                manager.unit_tags = unit_tags
                self.bot.base_manager.unit_tags -= manager.unit_tags    # 베이스에서 가져온 태그 빼기
                self.bot.tank_manager.unit_tags -= manager.unit_tags
                # 다른 매니저가 사용 중인 유닛 제외
                # unit_tags = unit_tags - self.bot.combat_manager.unit_tags
                

                press_init = True    # tank move가 1회 할당 되었음을 표시. HOLD로 바뀔때 다시 false됨


        elif manager.tactics is Tactics.FIRST_VIEW:
           # 현재 지도에 존재하는 그룹 유닛
            if manager.unit_tags == None:
                    group_units_tags = set()
            else:
                group_units_tags = manager.unit_tags
            group_units = self.bot.units.filter(lambda u: u.tag in group_units_tags)
                
            #group_units_tags = self.bot.units.tags & manager.unit_tags
            #group_units = self.bot.units.filter(lambda u: u.tag in group_units_tags)
            
            # 새 유닛 요청            
            new_units = self.bot.units & list()

            marines = self.bot.units(UnitTypeId.MARINE).owned 
            if group_units.of_type(UnitTypeId.MARINE).amount == 0 and marines.amount >= 1:
                new_units = new_units | marines.take(1)
                    
            unit_tags = (group_units | new_units).tags
            
            # 다른 매니저가 사용 중인 유닛 제외
            # unit_tags = unit_tags - self.bot.combat_manager.unit_tags
            manager.unit_tags = unit_tags

        else:
            raise NotImplementedError

    def debug(self):
        pass
        


                
class TestBot(sc2.BotAI):
    """
    flag 필드
    """
    global press_init   # tank move가 한번 할당되었는지, ATTACK일때 한번 true, HOLD될때 false가 됨
    global tank_drop_init

    def __init__(self, debug=False, *args, **kwargs):
        super().__init__()
        self.debug=debug
        self.step_manager = StepManager(self)
        self.strategic_manager = StrategicManager(self)        
        self.terrein_manager = TerreinManager(self)
        self.main_manager = Debuging(self, Tactics.MAIN)        # 메인부대
        self.middle_manager = Debuging(self, Tactics.MIDDLE)    # 중앙 지키는 부대
        self.vacant_manager = Debuging(self, Tactics.VACANT)    # 공터 지키는 부대
        self.base_manager = Debuging(self, Tactics.BASE)        # 사령부 지키는 부대
        self.tank_manager = Debuging(self, Tactics.TANK)        # 언덕에 탱크 부대
        self.tank_move_manager = Debuging(self, Tactics.TANK_MOVE)      # 압박할때 탱크 옮기는 부대
        self.anti_drop_manager = Debuging(self, Tactics.ANTI_DROP)      # 공터 근처에서 막는 부대
        self.tank_drop_manager = Debuging(self, Tactics.TANK_DROP)      # 상대방 탱크쪽에 공격하는 부대
        self.press_manager = Debuging(self, Tactics.PRESS)              # 압박가는 부대
        self.first_view_manager = Debuging(self, Tactics.FIRST_VIEW)    # 첫번째 시야 따는 부대
        self.assign_manager = AssignManager(self)
        #Flag 필드
        self.isTankDropTiming = False
        press_init = False
        tank_drop_init = False

    def on_start(self):
        self.step_manager.reset()
        self.strategic_manager.reset()
        self.terrein_manager.reset()
        self.main_manager.reset()
        self.middle_manager.reset()
        self.vacant_manager.reset()
        self.base_manager.reset()
        self.tank_manager.reset()
        self.tank_move_manager.reset()
        self.anti_drop_manager.reset()
        self.tank_drop_manager.reset()
        self.press_manager.reset()
        self.assign_manager.reset()
        self.assign_manager.assign(self.first_view_manager)
        
    async def on_step(self, iteration: int):
        """
        :param int iteration: 이번이 몇 번째 스텝인self.assign_manager = AssignManager(self)지를 인자로 넘겨 줌

        매 스텝마다 호출되는 함수
        주요 AI 로직은 여기에 구현
        """

        if self.step_manager.invalid_step():
            return list()

        if self.step_manager.step % 10 == 0 :
            self.terrein_manager.step()
            # 전략 변경
            self.strategic_manager.step()
        
        if self.step_manager.step % 2 == 0:
            self.tank_drop_manager.target = self.terrein_manager.enemy_tank_point()
            # 이게 탱크 드랍 타겟 설정하는 부분인데 적 탱크를 찾아서 넣는 코드로 고쳐야함
            self.assign_manager.assign(self.main_manager)
            self.assign_manager.assign(self.middle_manager)
            self.assign_manager.assign(self.vacant_manager)
            self.assign_manager.assign(self.base_manager)
            self.assign_manager.assign(self.tank_manager)
            self.assign_manager.assign(self.tank_move_manager)
            self.assign_manager.assign(self.anti_drop_manager)
            self.assign_manager.assign(self.tank_drop_manager)
            self.assign_manager.assign(self.press_manager)
            

        '''
        #########차이
        if self.step_manager.step > 100 and self.step_manager.step % 2 ==0:
            self.assign_manager.assign(self.anti_drop_manager)
        '''
            
            
        # 유닛 들이 수행할 액션은 리스트 형태로 만들어서,
        # do_actions 함수에 인자로 전달하면 게임에서 실행된다.
        # do_action 보다, do_actions로 여러 액션을 동시에 전달하는 것이 훨씬 빠르다.
        actions = list()
        actions += await self.main_manager.step()
        actions += await self.middle_manager.step()
        actions += await self.vacant_manager.step()
        actions += await self.base_manager.step()
        actions += await self.tank_manager.step()
        actions += await self.tank_move_manager.step()
        actions += await self.anti_drop_manager.step()
        actions += await self.tank_drop_manager.step()
        actions += await self.press_manager.step()
        actions += await self.first_view_manager.step()
        
        await self.do_actions(actions)

        if self.debug:
            self.assign_manager.debug()
            await self._client.send_debug()

