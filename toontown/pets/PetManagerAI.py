"""
Doodles (pets) for the Open Toontown server.

- The pet shop offers the same few doodles to everyone each day.
- Adopting creates the doodle in the database and links it to the toon.
- Doodles live at their owner's estate: when an estate loads, the doodle of
  every toon on that account is loaded from the database and let loose there.
  When the estate unloads, each doodle is saved and removed again.
- Doodles are saved every couple of minutes while they're out, and again when
  they leave, so their mood and tricks carry over.
"""
import random
import time

from direct.directnotify import DirectNotifyGlobal

from toontown.pets import PetDNA, PetMood, PetTraits, PetUtil
from toontown.pets.PetNameGenerator import PetNameGenerator

SAVE_INTERVAL = 120  # seconds between saves while a doodle is out
SECONDS_PER_DAY = 24 * 60 * 60


def _setterName(name):
    return 'set%s%s' % (name[0].upper(), name[1:])


class PetManagerAI:
    notify = DirectNotifyGlobal.directNotify.newCategory('PetManagerAI')

    def __init__(self, air):
        self.air = air
        self.zone2pets = {}    # estate zone -> set of doodle ids out in it
        self.pet2zone = {}     # doodle id -> estate zone (loading or out)
        self.nameGenerator = None
        taskMgr.doMethodLater(SAVE_INTERVAL, self.__saveTask, 'petMgr-save')

    # ---- pet shop ---------------------------------------------------------------
    def getAvailablePets(self, numPets=3, *args):
        """The same doodles for everyone, changing once a day."""
        day = int(time.time() // SECONDS_PER_DAY)
        rng = random.Random(day * 7919 + 17)
        return [rng.randint(1, 0x7fffffff) for i in range(numPets)]

    def createNewPetFromSeed(self, avId, seed, nameIndex=0, gender=0, safeZoneId=None):
        if self.nameGenerator is None:
            self.nameGenerator = PetNameGenerator()
        name = self.nameGenerator.getName(nameIndex)
        _, dna, traitSeed = PetUtil.getPetInfoFromSeed(seed, safeZoneId)
        dna = list(dna)
        PetDNA.setGender(dna, gender)
        fields = self.__newPetFields(avId, name, traitSeed, safeZoneId, dna)
        dclass = self.air.dclassesByName['DistributedPetAI']

        def created(petId):
            if not petId:
                self.notify.warning('Could not create a doodle for %s' % avId)
                return
            self.notify.info('%s adopted doodle %s (%s)' % (avId, petId, name))
            av = self.air.doId2do.get(avId)
            if av is not None:
                av.b_setPetId(petId)
            else:
                self.__setToonPetIdOffline(avId, petId)
            self.__spawnIfEstateLoaded(avId, petId)

        self.air.dbInterface.createObject(self.air.dbId, dclass, fields, created)

    def __newPetFields(self, ownerId, name, traitSeed, safeZone, dna):
        head, ears, nose, tail, body, color, colorScale, eyes, gender = dna
        fields = {'DcObjectType': ('DistributedPet',),
                  'setOwnerId': (ownerId,),
                  'setPetName': (name,),
                  'setTraitSeed': (traitSeed,),
                  'setSafeZone': (safeZone,),
                  'setHead': (head,), 'setEars': (ears,), 'setNose': (nose,), 'setTail': (tail,),
                  'setBodyTexture': (body,), 'setColor': (color,), 'setColorScale': (colorScale,),
                  'setEyeColor': (eyes,), 'setGender': (gender,),
                  'setLastSeenTimestamp': (int(time.time()),),
                  'setTrickAptitudes': ([],)}
        traits = PetTraits.PetTraits(traitSeed, safeZone)
        for traitName in PetTraits.getTraitNames():
            fields[_setterName(traitName)] = (traits.getTraitValue(traitName),)
        for component in PetMood.PetMood.Components:
            fields[_setterName(component)] = (0.0,)
        return fields

    def __setToonPetIdOffline(self, avId, petId):
        dclass = self.air.dclassesByName['DistributedToonAI']
        self.air.dbInterface.updateObject(self.air.dbId, avId, dclass, {'setPetId': (petId,)})

    def deleteToonsPet(self, avId):
        """The doodle is returned to the shop: it leaves the estate and the toon."""
        av = self.air.doId2do.get(avId)
        petId = av.getPetId() if av is not None else 0
        if petId:
            pet = self.air.doId2do.get(petId)
            if pet is not None and pet.__class__.__name__ == 'DistributedPetAI':
                pet.requestDelete()
            self.pet2zone.pop(petId, None)
            for pets in self.zone2pets.values():
                pets.discard(petId)
        if av is not None:
            av.b_setPetId(0)

    # ---- estates ------------------------------------------------------------------
    def __spawnIfEstateLoaded(self, avId, petId):
        estate = getattr(self.air.estateMgr, 'estate', {}).get(avId)
        if estate is not None and estate.zoneId in self.zone2pets:
            self.spawnPets(estate.zoneId, [petId])

    def spawnPets(self, zoneId, petIds):
        """Load each doodle from the database and let it loose in the estate zone."""
        self.zone2pets.setdefault(zoneId, set())
        for petId in petIds:
            if not petId or petId in self.pet2zone or petId in self.air.doId2do:
                continue
            self.pet2zone[petId] = zoneId
            self.air.dbInterface.queryObject(self.air.dbId, petId,
                                             lambda dclass, fields, petId=petId: self.__gotPet(petId, dclass, fields))

    def __gotPet(self, petId, dclass, fields):
        from toontown.pets.DistributedPetAI import DistributedPetAI
        zoneId = self.pet2zone.get(petId)
        if zoneId is None or zoneId not in self.zone2pets:
            self.pet2zone.pop(petId, None)
            return  # the estate unloaded while we were loading
        if not fields or dclass is None or dclass.getName() != 'DistributedPet':
            self.notify.warning('Doodle %s is missing from the database' % petId)
            self.pet2zone.pop(petId, None)
            return
        pet = DistributedPetAI(self.air)
        pet.doNotDeallocateChannel = True  # its id comes from the database, not our range
        for fieldName, args in fields.items():
            if fieldName == 'DcObjectType':
                continue
            setter = getattr(pet, fieldName, None)
            if setter is not None:
                try:
                    setter(*args)
                except Exception as e:
                    self.notify.warning('Doodle %s: could not set %s: %s' % (petId, fieldName, e))
        pet.generateWithRequiredAndId(petId, self.air.districtId, zoneId)
        self.zone2pets[zoneId].add(petId)

    def despawnPets(self, zoneId):
        """The estate is unloading: save every doodle in it and take it away."""
        for petId in list(self.zone2pets.pop(zoneId, ())):
            pet = self.air.doId2do.get(petId)
            if pet is not None:
                pet.requestDelete()  # saves via petLeaving
            self.pet2zone.pop(petId, None)
        for petId, zone in list(self.pet2zone.items()):
            if zone == zoneId:
                del self.pet2zone[petId]  # still loading; __gotPet will drop it

    def petLeaving(self, pet):
        """Called by DistributedPetAI.requestDelete, however it was removed."""
        self.savePet(pet)
        zoneId = self.pet2zone.pop(pet.doId, None)
        if zoneId is not None and zoneId in self.zone2pets:
            self.zone2pets[zoneId].discard(pet.doId)

    # ---- saving ---------------------------------------------------------------------
    def getPetFields(self, pet):
        """The doodle's saved fields, read from the live doodle."""
        fields = {}
        dclass = self.air.dclassesByName['DistributedPetAI']
        for i in range(dclass.getNumInheritedFields()):
            field = dclass.getInheritedField(i)
            if field.asMolecularField() or not field.isDb():
                continue
            name = field.getName()
            if not name.startswith('set'):
                continue
            getter = getattr(pet, 'get' + name[3:], None)
            if getter is None:
                continue
            try:
                fields[name] = (getter(),)
            except Exception:
                pass
        return fields

    def savePet(self, pet):
        if not getattr(pet, 'activated', 0) or not hasattr(pet, 'mood'):
            return  # not fully out yet: nothing new to save
        try:
            fields = self.getPetFields(pet)
            pet.lastSeenTimestamp = int(time.time())
            fields['setLastSeenTimestamp'] = (pet.lastSeenTimestamp,)
            self.air.dbInterface.updateObject(self.air.dbId, pet.doId, self.air.dclassesByName['DistributedPetAI'],
                                              fields)
        except Exception as e:
            self.notify.warning('Could not save doodle %s: %s' % (pet.doId, e))

    def __saveTask(self, task):
        for petId in list(self.pet2zone):
            pet = self.air.doId2do.get(petId)
            if pet is not None:
                self.savePet(pet)
        return task.again
