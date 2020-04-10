import ckan.plugins as p


class Data_DictionaryPlugin(p.SingletonPlugin):
    '''data dictionary plugin.'''

    p.implements(p.IRoutes,inherit=True)
    p.implements(p.IConfigurer)

    def before_map(self, map):
        map.connect(' temp', '/demp/demo',
                    controller='ckanext.dictionary.controller:DDController',
                    action='index')

        map.connect('data_dict_add','/dataset/dictionary/add/{id}',
                    controller='ckanext.dictionary.controller:DDController',
                    action='finaldict')

        map.connect('dataset_edit_dictionary','/dataset/dictionary/edit/{id}',
		            controller='ckanext.dictionary.controller:DDController',
                    action='edit_dictionary', 
                    ckan_icon='edit')

        map.connect('/dataset/new_resource/{id}',
                    controller='ckanext.dictionary.controller:DDController', 
                    action='new_resource_ext')

        map.connect('data dict button','/dataset/dictionary/new_dict/{id}',
                    controller='ckanext.dictionary.controller:DDController',
                    action="new_data_dictionary")

        map.connect('dataset_dictionary', '/dataset/dictionary/{id}',
                    controller='ckanext.dictionary.controller:DDController',
                    action='dictionary', 
                    ckan_icon='info-sign')
        return map

    def after_map(self, map):
        map.connect(' temp', '/demp/demo',
                    controller='ckanext.dictionary.controller:DDController',
                    action='index')

        map.connect('data_dict_add','/dataset/dictionary/add/{id}',
                    controller='ckanext.dictionary.controller:DDController',
                    action='finaldict')

        map.connect('dataset_edit_dictionary','/dataset/dictionary/edit/{id}',
                    controller='ckanext.dictionary.controller:DDController',
                    action='edit_dictionary', 
                    ckan_icon='edit')

        map.connect('/dataset/new_resource/{id}',
                    controller='ckanext.dictionary.controller:DDController', 
                    action='new_resource_ext')

        map.connect('dataset_dictionary', '/dataset/dictionary/{id}',
                    controller='ckanext.dictionary.controller:DDController',
                    action='dictionary', 
                    ckan_icon='info-sign')
        return map

    def update_config(self, config_):
        p.toolkit.add_template_directory(config_, 'templates')
        p.toolkit.add_public_directory(config_, 'public')
        p.toolkit.add_resource('fanstatic', 'dictionary')
