
__author__ = '이수민'

import random
from enum import Enum

import sc2
from sc2.position import Point2, Point3
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from toolbox.logger.colorize import Color as C

from IPython import embed


ARMY_TYPES = (UnitTypeId.MARINE, UnitTypeId.MARAUDER, 
    UnitTypeId.SIEGETANK, UnitTypeId.SIEGETANKSIEGED,
    UnitTypeId.MEDIVAC)

class DummyBot(sc2.BotAI):
    """
    아무것도 하지 않는 봇 예제
    """
    def __init__(self, debug=False, *args, **kwargs):
        super().__init__()
        self.debug = debug
        self.step_manager = StepManager(self)
        self.terrein_manager = TerreinManager(self)
        self.turret_kill_manager = CombatGroupManager(self, Tactics.TURRET_KILLER)
        self.middle_start_manager = CombatGroupManager(self, Tactics.MIDDLE_START_ARMY)
        self.sight_manager = CombatGroupManager(self, Tactics.SIGHT)
        self.assign_manager = AssignManager(self)
        self.strategic_manager = StrategicManager(self)

    def on_start(self):
        self.step_manager.reset()
        self.strategic_manager.reset()
        self.assign_manager.reset()
        self.turret_kill_manager.reset()
        self.middle_start_manager.reset()
        self.sight_manager.reset()
        self.terrein_manager.reset()

    async def on_step(self, iteration: int):
        """
        매니저 단위로 작업을 분리하여 보다 간단하게 on_step을 구현
        """
        if self.step_manager.invalid_step():
            return list()

        if self.step_manager.step % 2 == 0:
            # 전략 변경
            self.strategic_manager.step()

            # 지형정보 분석
            self.terrein_manager.step()

            # 새로운 공격지점 결정
            self.turret_kill_manager.target = self.terrein_manager.turret_point()
            self.sight_manager.target = self.terrein_manager.sight_point()
            self.middle_start_manager.target = self.terrein_manager.find_bunker()

            

            # 부대 구성 변경
            # self.assign_manager.step()
            self.assign_manager.assign(self.turret_kill_manager)
            self.assign_manager.assign(self.sight_manager)
            self.assign_manager.assign(self.middle_start_manager)


        actions = list()
        actions += await self.turret_kill_manager.step()
        actions += await self.middle_start_manager.step()
        actions += await self.sight_manager.step()

        await self.do_actions(actions)

        if self.debug:
            # 현재 전략 게임화면에 시각화
            self.strategic_manager.debug()
            # 지형정보를 게임 화면에 시각화
            self.terrein_manager.debug()
            self.turret_kill_manager.debug()
            self.middle_start_manager.debug()
            await self._client.send_debug()


class StepManager(object):
    """
    스텝 레이트 유지를 담당하는 매니저
    """
    def __init__(self, bot_ai):
        self.bot = bot_ai
        self.seconds_per_step = 0.25714  # on_step이 호출되는 주기
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

        # 가운데 시야확보하는 좌표
        self.sight_points_A = [
            Point2((40.87, 47.75)),
            Point2((29.36, 45.25)),
            Point2((50.17, 52.99)),
            Point2((64.65, 70.19)),
            Point2((40.87, 47.75)) # 이거 귀찮아서 하나 계산 안함
        ]

        self.sight_points_E = [
            Point2((46.81, 40.01)),
            Point2((58.47, 45.04)),
            Point2((35.2, 34.14)),
            Point2((21.89, 18.94)),
            Point2((40.87, 47.75))) 
        ]


        # 탱크지점
        self.tank_points_A = [
            Point2((35.8, 51.9)),
            Point2((27.91, 50.21)),
            Point2((36.8, 49.65)),
            Point2((42.50, 54.42)),
            Point2((66.29, 61.4)),
            Point2((31.5, 62.92))
        ]

        self.tank_points_E = [
            Point2((52.62, 36.18)),
            Point2((48.3, 38.14)),
            Point2((61.47, 38.18)),
            Point2((22.79,24.4)),
            Point2((45.27, 33)),
            Point2((56.06, 25.48))
        ]

        # 메인 부대 대기하는 좌표
        self.hold_points = [
            Point3((52,58,12)), # A꺼
            Point3((36,26,12)), # E꺼
        ]

        # 내 거점 방어하는 좌표
        self.base_defense_points =[
            Point3((24,53,12)), # A꺼
            Point3((63,35,12)), # E꺼
            ##################
            Point2((31.5,62.92)), #A
            Point2((56.06, 25.48))  #E
        ]
        

        # 내 공터 방어하는 좌표
        self.land_defense_points_A =[
            Point2((58.5, 63.5))
        ]

        self.land_defense_points_E =[
            Point2((22.79, 24.4))
        ]

        # 기습공격때 의료선 드랍하는 좌표
        self.surprise_points =[
            Point3((17,32,12)),
            Point3((71,56,12)),
        ]

        self.region_radius = 10
        self.current_point_idx = 2

    def reset(self):
        # 나와 적의 시작위치 설정
        self.start_location = self.bot.start_location
        self.enemy_start_location = self.bot.enemy_start_locations[0]

    def step(self):
        # 나와 적의 시작위치 설정
        if self.start_location is None:
            self.reset()

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

    def _map_abstraction(self):
        # 내 시작위치를 기준으로 가까운 지역부터 먼 지역까지 정렬함
        if self.start_location.distance2_to(self.strategic_points[0]) < 3:
            points = self.strategic_points
            occupancy = self.occupied_points()
        else:
            points = list(reversed(self.strategic_points))
            occupancy = list(reversed(self.occupied_points()))
        return points, occupancy

    def turret_point(self):
        """
        포탑 잡으러 시야 밝히는 해병 보낼 좌표 반환
        """
        if self.start_location.position.x<30:
            points = self.tank_points[2]   
        else:
            points = self.tank_points[3]
        return points

    def find_bunker(self):
        center = self.bot.units.of_type(UnitTypeId.COMMANDCENTER).owned
        bunkers = self.bot.units.of_type(UnitTypeId.BUNKER).owned
        bunkers = bunkers.sorted_by_distance_to(center[0])
        return bunkers[0]

    def frontline(self):
        """
        주력 병력을 투입할 전선을 결정
        """
        points, occupancy = self._map_abstraction()

        if self.bot.strategic_manager.strategy == Strategy.ATTACK:
            # 공격 전략일 때는 전선을 전진
            if occupancy[self.current_point_idx] > 0:
                self.current_point_idx += 1
                self.current_point_idx = min(4, self.current_point_idx)
            return strategic_points[self.current_point_idx]

        elif self.bot.strategic_manager.strategy == Strategy.HOLD:
            # 방어 전략일 때는 전선을 후퇴 좌표로 보냄
            if occupancy[self.current_point_idx] < 0:
                self.current_point_idx -= 1
                self.current_point_idx = max(1, self.current_point_idx)
            if start_location.position.x<30:
                return self.hold_points[0]
            else:
                return self.hold_points[1]
            

        # 어떤 조건도 만족시키지 않으면, 중앙에 유닛 배치
        return points[self.current_point_idx]

    def tank_points(self, index):   
        """
        탱크 좌표 반환 return type은 배열임~~~
        """

        if self.start_location.position.x<30:
            points = [self.tank_points[0],self.tank_points[2]]   
        else:
            points = [self.tank_points[1],self.tank_points[3]]
        return points
    
    def land_point(self):
        if self.start_location.position.x<30:
            points = self.land_defense_points[0]   
        else:
            points = self.land_defense_points[1]
        return points

    def my_point(self):
        if self.start_location.position.x<30:
            points = self.my_defense_points[0]   
        else:
            points = self.my_defense_points[1]
        return points

    def surprise_attack(self):
        if self.start_location.position.x<30:
            points = self.surprise_points[0]   
        else:
            points = self.surprise_points[1]
        return points
    
    def sight_point(self):
        if self.start_location.position.x<30:
            points = self.sight_points[0]   
        else:
            points = self.sight_points[1]
        return points

    def debug(self):
        """
        지형정보를 게임에서 시각화
        """
        # 각 지역마다, 내가 점령하고 있는지 아닌지 구의 색상으로 시각화
        for occ, point in zip(self.occupied_points(), self.strategic_points):
            color = Point3((255, 0, 0)) if occ > 0 else Point3((0, 0, 255))
            self.bot._client.debug_sphere_out(point, self.region_radius, color)


class CombatGroupManager(object):
    """
    개별 유닛에게 직접 명령을 내리는 매니저  그냥 step 꼭 필요함 잊지말기!!
    """
    def __init__(self, bot_ai, tactics):
        self.bot = bot_ai
        self.strategy = None
        self.target = None
        self.unit_tags = None
        # 그룹의 경계 범위
        self.perimeter_radious = 10
        self.tactics = tactics
        self.state = ''
    
    def reset(self):
        self.unit_tags = (self.bot.units & list()).tags

    def units(self):
        return self.bot.units.filter(lambda unit: unit.tag in self.unit_tags)

    async def step(self):
        actions = list()

        # 이 전투그룹에 속한 아군 유닛들
        units = self.units()

        if units.amount == 0 or self.target is None:
            return actions
        
        # 이 전투그룹 근처의 적군 유닛들
        enemy = self.bot.known_enemy_units.closer_than(
            self.perimeter_radious, units.center)

        for unit in units:
            if self.tactics == Tactics.TURRET_KILLER:
                actions += await self.turret_killer_step(unit, units, enemy)
            elif self.tactics == Tactics.MIDDLE_MAIN:
                actions += await self.middle_main_step(unit, units, enemy)
            elif self.tactics == Tactics.MIDDLE_START_ARMY:
                actions += await self.middle_start_step(unit, units, enemy)
            elif self.tactics == Tactics.LAND_DEFENSE:
                actions += await self.defense_step(unit, units, enemy)
            elif self.tactics == Tactics.POINT_DEFENSE:
                actions += await self.defense_step(unit, units, enemy)
            elif self.tactics == Tactics.SIGHT:
                actions += await self.sight_step(unit, units, enemy)
            elif self.tactics == Tactics.MIDDLE_TANK:
                actions += await self.middle_tank_step(unit, units, enemy)

            if self.bot.debug:
                # 모든 유닛의 공격목표롤 시각화
                if len(unit.orders) > 0:
                    # if unit.type_id == UnitTypeId.MARINE:
                    #     embed(); exit()
                    skill = unit.orders[0].ability.id.name
                    target = unit.orders[0].target
                    
                    if type(target) is Point3:
                        self.bot._client.debug_line_out(unit.position3d, target)
                        self.bot._client.debug_text_world(skill, target, size=16)

                    elif type(target) is int:
                        all_units = self.bot.units | self.bot.known_enemy_units
                        target_unit = all_units.find_by_tag(target)
                        if target_unit is not None:
                            target = target_unit.position3d
                            self.bot._client.debug_line_out(unit.position3d, target)
                            self.bot._client.debug_text_world(skill, target, size=16)


            return actions


        #if self.bot.debug:
            # 전투그룹의 중심점과 목표지점 시각화
        #    p1 = units.center
        #    p2 = self.target.to3
        #    self.bot._client.debug_sphere_out(
        #        Point3((p1.x, p1.y, 12)), 5, Point3((0, 255, 0)))
        #    self.bot._client.debug_line_out(
        #        Point3((p1.x, p1.y, 12)), p2, color=Point3((0, 255, 0)))
        #    self.bot._client.debug_sphere_out(
        #        self.target.to3, 5, Point3((0, 255, 0)))



    async def turret_killer_step(self, unit, friends, foes):    #첫번째 포탑 부수는 명령을 내린다.
        actions = list()
        order = unit.attack(self.target)
        actions.append(order)
        return actions
    
    async def middle_start_step(self, unit, friends, foes):     # 가운데 벙커에 들어가는 명령을 내린다.
        actions = list()
        middle_bunker = self.target
        if foes.amount > 0:
                if unit.health_percentage > 0.7 and \
                    not unit.has_buff(BuffId.STIMPACKMARAUDER):
                    # 스팀팩 사용
                    order = unit(AbilityId.EFFECT_STIM_MARAUDER)
                else:
                    # 가장 가까운 목표 공격
                    order = unit.attack(foes.closest_to(unit.position))
        else:
            if middle_bunker.cargo_used<middle_bunker.cargo_max:    #벙커에 자리 있는지 확인 이 코드 뭔가 매우매우 불안불안
                order = middle_bunker(AbilityId.LOAD_BUNKER, unit)

        actions.append(order)
        for u in friends:
            if self.bot.debug:
                text=[
                    f'number : {self.tactics}\n'
                    ]
                self.bot._client.debug_text_world(''.join(text), u.position3d, size=16)
        return actions

    async def middle_main_step(self, unit, friends, foes, point):   #commandcenter 에는 A인지 E인지 넣기
        actions = list()
        if self.strategy == ATTACK:
            order = unit.attack(self.target)   #상대방 거점 쳐들어가기
        elif self.strategy == HOLD:
            order = unit.attack(point)   #탱크 안맞는 곳 내 쪽 중앙에 있기
        elif self.strategy == SURPRISE_READY:
            order = unit.move(self.start_location)  # 내 사령부로 집합

            if unit.type_id == UnitTypeId.MEDIVAC:
                if self.state == 'ready':
                    if unit.distance_to(point) > 5:   # 움직이기
                        actions.append(unit.move(self.target))
                    elif len(unit.passengers) <= unit.cargo_max:    # 탑승인원의 최대치보다 적으면
                        if len(unit.orders) == 0:
                            assult_units = self.bot.units.filter(lambda u: u.tag in self.unit_tags).of_type(ARMY_TYPES) # 전부 다 태움
                            assult_units = assult_units.filter(lambda u: u.distance_to(unit.position) < 5)                    
                            if assult_units.amount > 0:
                                order = unit(AbilityId.LOAD, assult_units.first)
                                actions.append(order)
                    else:
                        self.state = 'go'

                elif self.state == 'go':
                    if unit.distance_to(self.start_location) > 11:    # 내 사령부로 감
                        actions.append(unit.move(self.start_location))    
                    else:
                        actions.append(unit.stop())
                        self.state = 'ready'


        elif self.strategy == SURPRISE:
            medivac = friends.of_type(UnitTypeId.MEDIVAC)

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
                            actions.append(unit.attack(medivac.center))
                    else:
                        if unit.distance_to(self.target) > 5:
                            actions.append(unit.attack(self.target))

            elif unit.type_id == UnitTypeId.MEDIVAC:

                if self.state == 'ready':
                    if unit.distance_to(self.target) > 5:   # 움직이기
                        actions.append(unit.move(self.target))
                    elif len(unit.passengers) <= unit.cargo_max:    # 탑승인원의 최대치보다 적으면
                        if len(unit.orders) == 0:
                            assult_units = self.bot.units.filter(lambda u: u.tag in self.unit_tags).of_type(ARMY_TYPES) # 전부 다 태움
                            assult_units = assult_units.filter(lambda u: u.distance_to(unit.position) < 5)                    
                            if assult_units.amount > 0:
                                order = unit(AbilityId.LOAD, assult_units.first)
                                actions.append(order)
                    else:
                        self.state = 'go'

                elif self.state == 'go':
                    if unit.distance_to(self.bot.terrein_manager.enemy_start_location) > 11:    #적 공터으로 처들어감 # 적 공터 좌표 얼른 알려줘!
                        actions.append(unit.move(self.bot.terrein_manager.enemy_start_location))    
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
                    if unit.distance_to(self.target) > 5:
                        actions.append(unit.move(defense_point)) 

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
                            if unit.distance_to(defense_point) > 5:   #그냥 집결 장소에 대기하기
                                order = unit.move(defense_point)
                                actions.append(order)

            elif unit.type_id == UnitTypeId.SIEGETANK:
                if foes.amount > 0:
                    # 근처에 적이 3이상 있으면 시즈모드
                    targets = self.bot.known_enemy_units.closer_than(7, friends.center)
                    if targets.amount > 3:
                        if len(unit.orders) == 0 or \
                            len(unit.orders) > 0 and unit.orders[0].ability.id not in (AbilityId.SIEGEMODE_SIEGEMODE, AbilityId.UNSIEGE_UNSIEGE):
                            order = unit(AbilityId.SIEGEMODE_SIEGEMODE)
                            actions.append(order)
                    else:
                        order = unit.attack(foes.closest_to(unit.position))
                        actions.append(order)
                else:
                    if unit.distance_to(defense_point) > 5:
                        # 어택땅으로 집결지로 이동
                        order = unit.attack(defense_point)
                        actions.append(order)
                    else:
                        # 대기할 때는 시즈모드로
                        if len(unit.orders) == 0 or \
                            len(unit.orders) > 0 and unit.orders[0].ability.id not in (AbilityId.SIEGEMODE_SIEGEMODE, AbilityId.UNSIEGE_UNSIEGE):
                            order = unit(AbilityId.SIEGEMODE_SIEGEMODE)
                            actions.append(order)

            elif unit.type_id == UnitTypeId.SIEGETANKSIEGED:
                # 목표지점에서 너무 멀리 떨어져 있으면 시즈모드 해제
                if unit.distance_to(defense_point) > 10:
                    if len(unit.orders) == 0 or \
                        len(unit.orders) > 0 and unit.orders[0].ability.id not in (AbilityId.SIEGEMODE_SIEGEMODE, AbilityId.UNSIEGE_UNSIEGE):
                        order = unit(AbilityId.UNSIEGE_UNSIEGE)
                        actions.append(order)
            actions.append(order)
        return actions
        
    async def defense_step(self, unit, friends, foes):
        actions = list()
        actions.append(unit.move(self.target))     #내 사령부 지킬 포인트로 가기
        if unit.type_id == UnitTypeId.MARINE:   #마린에게 내리는 명령
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
                if unit.distance_to(self.target) > 5:
                    actions.append(unit.move(self.target)) #지킬 포인트에서 그냥 그대로 있기
        
        elif unit.type_id == UnitTypeId.MARAUDER:   #불곰에게 내리는 명령
            if foes.amount > 0:
                if unit.health_percentage > 0.8 and \
                    not unit.has_buff(BuffId.STIMPACKMARAUDER):
                    # 스팀팩 사용
                    order = unit(AbilityId.EFFECT_STIM_MARAUDER)
                else:
                    # 가장 가까운 목표 공격
                    order = unit.attack(foes.closest_to(unit.position))
                actions.append(order)
            else:
                if unit.distance_to(self.target) > 5:
                    actions.append(unit.move(self.target)) #지킬 포인트에서 그냥 그대로 있기
        
        elif unit.type_id == UnitTypeId.MEDIVAC: #메딕한테 내릴 명령
            if unit.distance_to(friends.center) > 5:
                actions.append(unit.attack(friends.center))     #내 아군 주변가까이에 있기
        
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
                        if unit.distance_to(self.target) > 5:   #그냥 집결 장소에 대기하기
                            order = unit.move(self.target)
                            actions.append(order)

        elif unit.type_id == UnitTypeId.SIEGETANK:
            if foes.amount > 0:
                # 근처에 적이 3이상 있으면 시즈모드
                targets = self.bot.known_enemy_units.closer_than(7, friends.center)
                if targets.amount > 3:
                    if len(unit.orders) == 0 or \
                        len(unit.orders) > 0 and unit.orders[0].ability.id not in (AbilityId.SIEGEMODE_SIEGEMODE, AbilityId.UNSIEGE_UNSIEGE):
                        order = unit(AbilityId.SIEGEMODE_SIEGEMODE)
                        actions.append(order)
                else:
                    order = unit.attack(foes.closest_to(unit.position))
                    actions.append(order)
            else:
                if unit.distance_to(self.target) > 5:
                    # 어택땅으로 집결지로 이동
                    order = unit.attack(self.target)
                    actions.append(order)
                else:
                    # 대기할 때는 시즈모드로
                    if len(unit.orders) == 0 or \
                        len(unit.orders) > 0 and unit.orders[0].ability.id not in (AbilityId.SIEGEMODE_SIEGEMODE, AbilityId.UNSIEGE_UNSIEGE):
                        order = unit(AbilityId.SIEGEMODE_SIEGEMODE)
                        actions.append(order)

        elif unit.type_id == UnitTypeId.SIEGETANKSIEGED:
            # 목표지점에서 너무 멀리 떨어져 있으면 시즈모드 해제
            if unit.distance_to(self.target) > 10:
                if len(unit.orders) == 0 or \
                    len(unit.orders) > 0 and unit.orders[0].ability.id not in (AbilityId.SIEGEMODE_SIEGEMODE, AbilityId.UNSIEGE_UNSIEGE):
                    order = unit(AbilityId.UNSIEGE_UNSIEGE)
                    actions.append(order)
        return actions

    async def middle_tank_step(self, unit, friends, foes):
        actions = list()
        tanks = (friends.of_type(UnitTypeId.SIEGETANK)|friends.of_type(UnitTypeId.SIEGETANKSIEGED))
        tanks = tanks.sorted(keyfn=lambda u: u.tag)
        
        if tanks[0].exists:
            tank1 = tanks[0]
            if tank1.distance_to(self.target[0]) > 3:
                actions.append(tanks[0].move(self.target[0]))
            else:
                if len(unit.orders) == 0 or \
                        len(unit.orders) > 0 and unit.orders[0].ability.id not in (AbilityId.SIEGEMODE_SIEGEMODE, AbilityId.UNSIEGE_UNSIEGE):
                        order = unit(AbilityId.SIEGEMODE_SIEGEMODE)
                        actions.append(order)

        if tanks[1].exists:
            tank2 = tanks[1]
            if tank2.distance_to(self.target[1]) > 3:
                actions.append(tanks[1].move(self.target[1]))
            else:
                if len(unit.orders) == 0 or \
                        len(unit.orders) > 0 and unit.orders[0].ability.id not in (AbilityId.SIEGEMODE_SIEGEMODE, AbilityId.UNSIEGE_UNSIEGE):
                        order = unit(AbilityId.SIEGEMODE_SIEGEMODE)
                        actions.append(order)
        return actions

    async def sight_step(self, unit, friends, foes):
        actions = list()
        actions.append(unit.move(self.target))
        return actions

    def debug(self):
        text = f'Strategy: {self.strategy}'
        self.bot._client.debug_text_screen(
            '\n\n'.join(text), pos=(0.02, 0.02), size=10)




class AssignManager():
    def __init__(self, bot_ai, *args, **kwargs):
        self.bot = bot_ai

    def reset(self):
        pass

    def assign(self, manager):

        units = self.bot.units

        if manager.tactics is Tactics.TURRET_KILLER:
            
            #group_units_tags = manager.unit_tags
            #group_units = self.bot.units.filter(lambda u: u.tag in group_units_tags)
            
            # 다른 부대가 쓰고있는 유닛은 제외함
            
            #new_units.tags = new_units.tags - self.bot.middle_start_manager.unit_tags
            #new_units.tags = new_units.tags - self.bot.middle_main_manager.unit_tags
            #new_units.tags = new_units.tags - self.bot.land_defense_manager.unit_tags            
            #new_units.tags = new_units.tags - self.bot.point_defense_manager.unit_tags
            #new_units.tags = new_units.tags - self.bot.middle_tank_manager.unit_tags
            
            if self.bot.step_manager.step<30 :    #포탑 깨지기 전이면 새 유닛 요청
                if manager.unit_tags == None :
                    new_units = self.bot.units & list()
                
                    marines = self.bot.units(UnitTypeId.MARINE).owned   # 마린 1
                    if marines.amount > 1:
                        new_units = marines.take(1)

                    unit_tags = new_units.tags
                    manager.unit_tags = unit_tags
            else:       # 일정시간 지난 후 포탑 깨지면 메인유닛에 합류
                self.bot.middle_start_manager.unit_tags = (manager.unit_tags|self.bot.middle_start_manager.unit_tags)
                manager.unit_tags = set()


        elif manager.tactics is Tactics.SIGHT:          #시야따는 부대
            if manager.unit_tags == None:
                group_units_tags = set()

            else:
                group_units_tags = manager.unit_tags
            group_units = self.bot.units.filter(lambda u: u.tag in group_units_tags)
            
            # 새 유닛 요청            
            new_units = self.bot.units & list()

            medivacs = self.bot.units.of_type(UnitTypeId.MEDIVAC).owned
            if group_units.of_type(UnitTypeId.MEDIVAC).amount == 0 and medivacs.amount > 0:
                new_units = new_units | medivacs.tags_not_in(group_units.tags).take(1)
            unit_tags = (group_units | new_units).tags
            manager.unit_tags = unit_tags


        elif manager.tactics is Tactics.MIDDLE_START_ARMY:
            bunker = manager.target


            if manager.unit_tags == None:
                group_units_tags = set()
            else:
                group_units_tags = manager.unit_tags
            group_units = self.bot.units.filter(lambda u: u.tag in group_units_tags)

            passengers = list()
            for passenger in bunker.passengers:
                passengers.append(passenger)
            # 탑승 유닛까지 포함
            group_units = group_units | passengers

            # 새 유닛 요청            
            new_units = self.bot.units & list()

            marines = self.bot.units(UnitTypeId.MARINE).owned # 마린 5마리
            if group_units.of_type(UnitTypeId.MARINE).amount < 6:
                new_units = (new_units | marines.tags_not_in(group_units.tags).take(1))
#                amount = 5-group_units.of_type(UnitTypeId.MARINE).amount
#                if amount < marines.amount:
#                    new_units = (new_units | marines.tags_not_in(group_units.tags).take(amount))
#                else :
#                    new_units = (new_units | marines.tags_not_in(group_units.tags).take(1))

            marauders = self.bot.units(UnitTypeId.MARAUDER).owned   # 불곰 1
            if group_units.of_type(UnitTypeId.MARAUDER).amount < 1 and marauders.amount > 0:
                new_units = (new_units | marauders.tags_not_in(group_units.tags).take(1))
            
            unit_tags = (group_units | new_units).tags - self.bot.turret_kill_manager.unit_tags 

            if bunker.health_percentage<0.15:      # 내 벙커 가운데 부숴지면 메인 부대에 합류
                self.bot.middle_main_manager.unit_tags = (manager.unit_tags|self.bot.middle_main_manager.unit_tags)
            else:
                manager.unit_tags = unit_tags
               


        elif manager.tactics is Tactics.MIDDLE_MAIN:
            units = self.bot.units.of_type(ARMY_TYPES).owned
            unit_tags = units.tags
            unit_tags = unit_tags - self.bot.turret_kill_manager.unit_tags
            unit_tags = unit_tags - self.bot.middle_start_manager.unit_tags
            unit_tags = unit_tags - self.bot.middle_main_manager.unit_tags
            unit_tags = unit_tags - self.bot.land_defense_manager.unit_tags            
            unit_tags = unit_tags - self.bot.point_defense_manager.unit_tags
            unit_tags = unit_tags - self.bot.middle_tank_manager.unit_tags
            manager.unit_tags = unit_tags            

        
        elif manager.tactics is Tactics.MIDDLE_TANK:
            group_units_tags = self.bot.units.tags & manager.unit_tags
            group_units = self.bot.units.filter(lambda u: u.tag in group_units_tags)            

            # 새 유닛 요청
            new_units = self.bot.units & list()
            tanks = self.bot.units.of_type(SIEGETANK).owned
            if group_units.of_type(UnitTypeId.SIEGETANK).amount <2 and tanks.amount > 0:
                new_units = new_units | tanks.tags_not_in(group_units.tags).take(1)
            unit_tags = (group_units | new_units).tags

            manager.unit_tags = unit_tags

            

        elif manager.tactics is Tactics.POINT_DEFENSE or managers.tactics is Tactics.LAND_DEFENSE:  # 거점 방어와 공터 방어
            # 마린 3 불곰1 사신 1 의료선 1
            # 현재 지도에 존재하는 그룹 유닛
            group_units_tags = self.bot.units.tags & manager.unit_tags
            group_units = self.bot.units.filter(lambda u: u.tag in group_units_tags)

            # 새 유닛 요청            
            new_units = self.bot.units & list()

            medivacs = self.bot.units(UnitTypeId.MEDIVAC).owned # 의료선 1개
            if group_units.of_type(UnitTypeId.MEDIVAC).amount == 0 and medivacs.amount > 1:
                new_units = new_units | medivacs.tags_not_in(group_units.tags).take(1)

            marauders = self.bot.units(UnitTypeId.MARAUDER).owned   # 불곰 1
            if group_units.of_type(UnitTypeId.MARAUDER).amount == 0 and marauders.amount > 1:
                new_units = new_units | marauders.tags_not_in(group_units.tags).take(1)
            
            marines = self.bot.units(UnitTypeId.MARINE).owned   # 마린 1
            if group_units.of_type(UnitTypeId.MARINE).amount <3 and marines.amount>1:
                new_units = new_units | marines.tags_not_int(group_units.tags).take(1)

            reapers = self.bot.units(UnitTypeId.REAPER).owned   # 사신 1
            if group_units.of_type(UnitTypeId.REAPER).amount <3 and reapers.amount > 1:
                new_units = new_units | reapers.tags_not_int(group_units.tags).take(1)    
            
            # 다른 부대가 쓰고있는 유닛들 제외
            new_units.tags = new_units.tags - self.bot.turret_kill_manager.unit_tags
            new_units.tags = new_units.tags - self.bot.middle_start_manager.unit_tags
            new_units.tags = new_units.tags - self.bot.middle_main_manager.unit_tags
            new_units.tags = new_units.tags - self.bot.middle_tank_manager.unit_tags
            if(manager.tactics is Tactics.POINT_DEFENSE):
                new_units.tags = new_units.tags - self.bot.land_defense_manager.unit_tags            
            if(manager.tactics is Tactics.LAND_DEFENSE):
                new_units.tags = new_units.tags - self.bot.point_defense_manager.unit_tags
            unit_tags = (group_units | new_units).tags
            
            manager.unit_tags = unit_tags

        else:
            raise NotImplementedError



    


class Strategy(Enum):
    """
    Bot이 선택할 수 있는 전략
    Strategy Manager는 언제나 이 중에 한가지 상태를 유지하고 있어야 함
    """
    NONE = 0
    ATTACK = 1
    HOLD = 2
    SURPRISE_READY = 3    # 기습 공격


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
        elif self.bot.supply_cap<=50 and self.bot.supply_used / (self.bot.supply_cap + 0.01) > 0.8: # 더이상 물러설 곳이 없다면 기습공격
            self.strategy = Strategy.SURPRISE_READY
        
        #elif : 주력부대가 내 사령부에 와서 다 레디상태이면 기습공격 시작

        
        else:
            self.strategy = Strategy.HOLD

    def debug(self):
        text = [
            f'Strategy: {self.strategy}',
            f'Supply used: {self.bot.supply_used / (self.bot.supply_cap + 0.01):1.3f}'
        ]
        self.bot._client.debug_text_screen(
            '\n\n'.join(text), pos=(0.02, 0.02), size=10)
    

    



class Tactics(Enum):
    NORMAL = 0
    TURRET_KILLER = 1
    MIDDLE_START_ARMY = 2
    MIDDLE_MAIN = 3
    POINT_DEFENSE = 4
    LAND_DEFENSE = 5
    MIDDLE_TANK = 6
    SIGHT = 7






 #탱크 포지션
        self.tank_tags = [None, None, None, None, None, None]
        self.tank_units = [set(), set(), set(), set(), set(), set()]
        #탱크 보조 해병 포지션
        self.tank_marine_tags = [None, None, None, None, None, None]
        self.tank_marine_units = [set(), set(), set(), set(), set(), set()]
        
    def reset(self):
        self.unit_tags = (self.bot.units & list()).tags
        #탱크
        for i in range(6):
            self.tank_tags[i] = (self.bot.units & list()).tags
            self.tank_marine_tags[i] = (self.bot.units & list()).tags
        #탱크 보조 해병 포지션

     async def tank_step(self, units):
        actions = list()

        for i in range(6):
            self.tank_units[i] = self.get_one_tank(units, i)

        tank_units = self.tank_units
    
        return actions
    
    def get_one_tank(self, units, number):
        self.number = number

        group_units_tags = units.tags & self.tank_tags[number]
        group_units = units.filter(lambda u: u.tag in group_units_tags)

        tags_in_tank_tags = set()

        for i in range(6):
            tags_in_tank_tags = tags_in_tank_tags | self.tank_tags[i]
            
        new_units = self.bot.units & list()

        has_left = False

        
        left_index = 0

        for i in range(5-number):
            if len(self.tank_units[number+1]) > 0 :
                has_left = True
                left_index = number+1
                break
        
        
        if has_left == True and (group_units.of_type(UnitTypeId.MARAUDER)).amount == 0:
            new_units = self.tank_units[left_index]
            new_units_for_left = self.bot.units & list()
            new_units_for_left = new_units_for_left | units.tags_not_in(tags_in_tank_tags).take(1)
            self.tank_tags[left_index] = (new_units_for_left).tags

        
        if has_left == False:
            if (group_units.of_type(UnitTypeId.MARAUDER)).amount == 0 and units.amount>=1:
                new_units = new_units | units.tags_not_in(tags_in_tank_tags).take(1)

        unit_tags = (group_units | new_units).tags

        self.tank_tags[number] = unit_tags

        return group_units | new_units

        


        







